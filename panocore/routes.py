"""Flask route registration for PanoCOTA."""

from __future__ import annotations

import copy
import csv
import os
import threading
import uuid

from flask import Flask, jsonify, render_template, request, send_from_directory

from .publish_pages import export_and_publish
from .graph.service import generate_graph_asset_with_info, get_graph_cache_signature
from .default_tour import get_empty_tour
from .settings import DATA_DIR, GRAPHS_DIR, IMAGES_2D_DIR, IMAGES_360_DIR, LEGACY_IMAGES_DIR
from .storage import (
    clear_graph_cache_for_tour,
    data_dir_for_tour,
    delete_tour,
    ensure_tour_asset_dirs,
    graph_dir_for_tour,
    image_2d_dir_for_tour,
    image_dir_for_tour,
    is_allowed_data_file,
    is_allowed_image,
    list_2d_images_for_tour,
    list_panorama_images_for_tour,
    list_tour_names,
    list_csvs_for_tour,
    load_tour,
    panorama_dir_for_tour,
    read_graph_cache_signature_for_tour,
    normalize_tour_name,
    sanitize_filename,
    save_tour,
    write_graph_cache_signature_for_tour,
    write_uploaded_file,
)


GRAPH_PREVIEW_MAX_POINTS_DEFAULT = 2200


def register_routes(app: Flask) -> None:
    """Register HTTP routes on the Flask application instance."""

    current_tour = get_empty_tour()
    current_tour_name = normalize_tour_name(None)
    ensure_tour_asset_dirs(current_tour_name)
    publish_jobs: dict[str, dict] = {}
    publish_jobs_lock = threading.Lock()

    def validate_tour_payload(payload: dict) -> str | None:
        """Return an error string when payload is invalid, else None."""
        if "scenes" not in payload or not isinstance(payload["scenes"], dict):
            return "Payload must include a scenes dictionary."

        meta = payload.get("meta", {})
        start_scene = meta.get("startScene")
        if start_scene and start_scene not in payload["scenes"]:
            return "meta.startScene must reference an existing scene."
        return None

    def refresh_graph_cache_for_signature(tour_name: str) -> int:
        """Clear and refresh a tour's graph cache only when renderer signature changed."""
        normalized = normalize_tour_name(tour_name)
        current_signature = get_graph_cache_signature()
        previous_signature = read_graph_cache_signature_for_tour(normalized)
        removed = 0
        if previous_signature and previous_signature != current_signature:
            removed = clear_graph_cache_for_tour(normalized)
        if previous_signature != current_signature:
            write_graph_cache_signature_for_tour(normalized, current_signature)
        return removed

    def request_tour_name(default: str | None = None) -> str:
        """Resolve a requested tour name from query/form with fallback to active tour."""
        requested = (request.args.get("tour") or request.form.get("tour") or "").strip()
        if requested:
            return normalize_tour_name(requested)
        return normalize_tour_name(default or current_tour_name)

    def _set_publish_job(job_id: str, **updates) -> dict:
        with publish_jobs_lock:
            job = publish_jobs.setdefault(job_id, {"status": "queued", "progress": 0, "message": "Queued."})
            job.update(updates)
            return copy.deepcopy(job)

    def _get_publish_job(job_id: str) -> dict | None:
        with publish_jobs_lock:
            job = publish_jobs.get(job_id)
            return copy.deepcopy(job) if job is not None else None

    def _publish_worker(job_id: str, payload: dict) -> None:
        def _progress(percent: int, message: str) -> None:
            _set_publish_job(job_id, status="running", progress=int(percent), message=message)

        try:
            _set_publish_job(job_id, status="running", progress=0, message="Starting publish...")
            exported, repo_name, pages_url, pages_warning = export_and_publish(
                tours=payload["tours"],
                owner=payload["owner"],
                token=payload["token"],
                repo=payload["repo"],
                branch=payload["branch"],
                private_repo=payload["private_repo"],
                github_org=payload["github_org"],
                progress=_progress,
            )
            _set_publish_job(
                job_id,
                status="completed",
                progress=100,
                message="Publish completed.",
                result={
                    "exported": exported,
                    "repo": repo_name,
                    "owner": payload["owner"],
                    "branch": payload["branch"],
                    "repoUrl": f"https://github.com/{payload['owner']}/{repo_name}",
                    "pagesUrl": pages_url,
                    "pagesWarning": pages_warning,
                },
            )
        except Exception as exc:
            _set_publish_job(job_id, status="failed", progress=100, message="Publish failed.", error=str(exc))

    @app.get("/")
    def index():
        """Render the single-page editor UI."""
        return render_template("index.html")

    @app.get("/viewer")
    def viewer_index():
        """Render read-only local viewer UI for loading saved tours."""
        return render_template("viewer.html")

    @app.get("/help/new-tour")
    def new_tour_help():
        """Render step-by-step instructions for creating a new tour."""
        return render_template("help_new_tour.html")

    @app.get("/api/tour")
    def get_tour():
        """Return current in-memory tour configuration JSON."""
        return jsonify(current_tour)

    @app.post("/api/tour")
    def update_tour():
        """Validate and update in-memory tour JSON payload."""
        nonlocal current_tour
        payload = request.get_json(silent=True)
        if not payload:
            return jsonify({"error": "Missing JSON payload."}), 400

        error = validate_tour_payload(payload)
        if error:
            return jsonify({"error": error}), 400

        current_tour = copy.deepcopy(payload)
        return jsonify({"ok": True})

    @app.post("/api/tour/save")
    def save_tour_manually():
        """Persist the provided tour payload or current in-memory tour to disk."""
        nonlocal current_tour, current_tour_name
        body = request.get_json(silent=True) or {}
        if isinstance(body, dict) and "name" in body:
            name = normalize_tour_name(body.get("name"))
            payload = body.get("tour")
        else:
            name = normalize_tour_name(None)
            payload = body if isinstance(body, dict) and "scenes" in body else None

        if payload is not None:
            error = validate_tour_payload(payload)
            if error:
                return jsonify({"error": error}), 400
            current_tour = copy.deepcopy(payload)

        saved_name = save_tour(current_tour, name=name)
        current_tour_name = saved_name
        ensure_tour_asset_dirs(current_tour_name)
        return jsonify({"ok": True, "name": saved_name})

    @app.post("/api/tour/load")
    def load_tour_manually():
        """Load persisted tour from disk into current in-memory state."""
        nonlocal current_tour, current_tour_name
        body = request.get_json(silent=True) or {}
        name = normalize_tour_name(body.get("name"))
        try:
            loaded = load_tour(name=name)
        except FileNotFoundError:
            return jsonify({"error": f"No saved tour found for '{name}'."}), 404

        error = validate_tour_payload(loaded)
        if error:
            return jsonify({"error": f"Saved tour is invalid: {error}"}), 400

        current_tour_name = name
        ensure_tour_asset_dirs(current_tour_name)
        removed_stale_graphs = refresh_graph_cache_for_signature(current_tour_name)
        current_tour = copy.deepcopy(loaded)
        return jsonify(
            {
                "ok": True,
                "tour": current_tour,
                "name": name,
                "removedStaleGraphs": removed_stale_graphs,
            }
        )

    @app.post("/api/tour/close")
    def close_tour():
        """Close the current tour while preserving graph cache for faster reopen."""
        nonlocal current_tour, current_tour_name
        closed_name = current_tour_name
        current_tour = get_empty_tour()
        current_tour_name = normalize_tour_name(None)
        ensure_tour_asset_dirs(current_tour_name)
        return jsonify({"ok": True, "closed": closed_name, "removedGraphs": 0, "tour": current_tour})

    @app.get("/api/tours")
    def list_tours():
        """Return available saved tour names."""
        return jsonify({"ok": True, "tours": list_tour_names()})

    @app.get("/api/viewer/tours")
    def list_tours_for_viewer():
        """Return available saved tour names for read-only viewer."""
        return jsonify({"ok": True, "tours": list_tour_names()})

    @app.get("/api/viewer/tour")
    def get_tour_for_viewer():
        """Load a saved tour by name for read-only viewer without changing active editor tour."""
        name_raw = (request.args.get("name") or "").strip()
        if not name_raw:
            return jsonify({"error": "name query parameter is required."}), 400

        name = normalize_tour_name(name_raw)
        try:
            loaded = load_tour(name=name)
        except FileNotFoundError:
            return jsonify({"error": f"No saved tour found for '{name}'."}), 404

        error = validate_tour_payload(loaded)
        if error:
            return jsonify({"error": f"Saved tour is invalid: {error}"}), 400

        refresh_graph_cache_for_signature(name)

        return jsonify({"ok": True, "tour": loaded, "name": name})

    @app.post("/api/tour/delete")
    def delete_tour_manually():
        """Delete a named saved tour file from disk."""
        body = request.get_json(silent=True) or {}
        name = normalize_tour_name(body.get("name"))
        deleted = delete_tour(name)
        if not deleted:
            return jsonify({"error": f"No saved tour found for '{name}'."}), 404
        return jsonify({"ok": True, "name": name})

    @app.post("/api/tour/reset")
    def reset_tour():
        """Reset current in-memory tour to an empty payload."""
        nonlocal current_tour
        current_tour = get_empty_tour()
        return jsonify({"ok": True})

    @app.post("/api/publish/github")
    def publish_to_github():
        """Export tours and publish static package to a GitHub repository."""
        body = request.get_json(silent=True) or {}

        publish_all = bool(body.get("all"))
        owner = str(body.get("owner") or "").strip()
        repo = str(body.get("repo") or "").strip()
        branch = str(body.get("branch") or "main").strip() or "main"
        github_org = bool(body.get("githubOrg"))
        private_repo = bool(body.get("privateRepo"))

        if not owner:
            return jsonify({"error": "GitHub owner is required."}), 400

        if publish_all:
            tours = list_tour_names()
        else:
            requested_name = normalize_tour_name(body.get("tour") or current_tour_name)
            tours = [requested_name] if requested_name else []

        if not tours:
            return jsonify({"error": "No tours selected for publish."}), 400

        available = set(list_tour_names())
        missing = [name for name in tours if name not in available]
        if missing:
            return jsonify({"error": f"These tours are not saved to disk: {', '.join(missing)}"}), 400

        request_token = str(body.get("githubToken") or "").strip()
        token = request_token or str(os.getenv("GITHUB_TOKEN") or "").strip()
        if not token:
            return jsonify({"error": "Provide a GitHub token in the publish form, or set GITHUB_TOKEN on the server environment."}), 400

        job_id = uuid.uuid4().hex
        _set_publish_job(job_id, status="queued", progress=0, message="Queued.")

        thread_payload = {
            "tours": tours,
            "owner": owner,
            "token": token,
            "repo": repo,
            "branch": branch,
            "private_repo": private_repo,
            "github_org": github_org,
        }
        thread = threading.Thread(target=_publish_worker, args=(job_id, thread_payload), daemon=True)
        thread.start()

        return jsonify({"ok": True, "jobId": job_id, "statusUrl": f"/api/publish/github/status/{job_id}"}), 202

    @app.get("/api/publish/github/status/<job_id>")
    def publish_github_status(job_id: str):
        """Return the current status for a background GitHub publish job."""
        job = _get_publish_job(job_id)
        if job is None:
            return jsonify({"error": "Unknown publish job."}), 404
        return jsonify({"ok": True, "jobId": job_id, **job})

    def _upload_image_to_dir(target_dir_resolver, path_prefix: str):
        """Upload image file into the requested tour directory and return response payload."""
        file = request.files.get("image")
        if file is None or file.filename is None or file.filename.strip() == "":
            return jsonify({"error": "No file uploaded."}), 400

        if not is_allowed_image(file.filename):
            return jsonify({"error": "Only jpg, jpeg, png, webp are allowed."}), 400

        filename = sanitize_filename(file.filename)
        target_tour_name = request_tour_name()
        target_dir = target_dir_resolver(target_tour_name)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        write_uploaded_file(file, target_path)

        return jsonify(
            {
                "ok": True,
                "path": f"/{path_prefix}/{target_tour_name}/{filename}",
                "filename": filename,
                "tour": target_tour_name,
            }
        )

    @app.post("/api/upload_360")
    def upload_panorama_image():
        """Upload and store 360 panorama image under per-tour 360 directory."""
        return _upload_image_to_dir(panorama_dir_for_tour, "images360")

    @app.post("/api/upload_2d")
    def upload_2d_image():
        """Upload and store 2D image under per-tour 2D directory."""
        return _upload_image_to_dir(image_2d_dir_for_tour, "images2d")

    @app.post("/api/upload")
    def upload_image_legacy():
        """Legacy upload endpoint retained for backward compatibility (maps to 360)."""
        return _upload_image_to_dir(panorama_dir_for_tour, "images360")

    @app.get("/api/images_360")
    def list_panorama_images():
        """Return available 360 panorama filenames for the requested tour."""
        tour_name = request_tour_name()
        names = list_panorama_images_for_tour(tour_name)
        return jsonify({"ok": True, "images": names, "tour": tour_name})

    @app.get("/api/images_2d")
    def list_2d_images():
        """Return available 2D image filenames for the requested tour."""
        tour_name = request_tour_name()
        names = list_2d_images_for_tour(tour_name)
        return jsonify({"ok": True, "images": names, "tour": tour_name})

    @app.get("/api/images")
    def list_images_legacy():
        """Legacy image listing endpoint retained for compatibility (returns 360 list)."""
        tour_name = request_tour_name()
        names = list_panorama_images_for_tour(tour_name)
        return jsonify({"ok": True, "images": names, "tour": tour_name})

    @app.post("/api/upload_csv")
    def upload_csv():
        """Upload and store CSV data file under the requested tour directory."""
        file = request.files.get("datafile")
        if file is None or file.filename is None or file.filename.strip() == "":
            return jsonify({"error": "No CSV file uploaded."}), 400

        if not is_allowed_data_file(file.filename):
            return jsonify({"error": "Only .csv files are allowed."}), 400

        filename = sanitize_filename(file.filename)
        tour_name = request_tour_name()
        data_dir = data_dir_for_tour(tour_name)
        data_dir.mkdir(parents=True, exist_ok=True)
        target_path = data_dir / filename
        write_uploaded_file(file, target_path)

        return jsonify(
            {
                "ok": True,
                "filename": filename,
                "path": f"/static/data/{tour_name}/{filename}",
                "tour": tour_name,
            }
        )

    @app.get("/api/csvs")
    def list_csv_files():
        """Return available CSV filenames in the requested tour data directory."""
        tour_name = request_tour_name()
        names = list_csvs_for_tour(tour_name)
        return jsonify({"ok": True, "files": names, "tour": tour_name})

    @app.get("/api/csv_columns")
    def get_csv_columns():
        """Return header columns for a requested CSV file in the requested tour."""
        csv_name = sanitize_filename((request.args.get("csv") or "").strip())
        if not csv_name:
            return jsonify({"error": "csv query parameter is required."}), 400
        if not is_allowed_data_file(csv_name):
            return jsonify({"error": "csv must reference a .csv file."}), 400

        tour_name = request_tour_name()
        csv_path = data_dir_for_tour(tour_name) / csv_name
        if not csv_path.exists():
            # Backward-compatibility for legacy global CSV files.
            csv_path = DATA_DIR / csv_name
        if not csv_path.exists():
            return jsonify({"error": "CSV file not found."}), 404

        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            headers = next(reader, [])

        return jsonify({"ok": True, "csv": csv_name, "columns": headers, "tour": tour_name})

    @app.get("/api/graph")
    def get_graph():
        """Generate and return URL for graph image derived from CSV query params."""
        graph_tour_name = request_tour_name()
        csv_name = (request.args.get("csv") or "").strip()
        x_col = (request.args.get("x") or "").strip()
        y_cols = [value.strip() for value in request.args.getlist("y") if value and value.strip()]
        if not y_cols:
            legacy_y = (request.args.get("y") or "").strip()
            if legacy_y:
                y_cols = [legacy_y]
        subplots_raw = (request.args.get("subplots") or "").strip()
        y_label = (request.args.get("yLabel") or "").strip()
        y_unit = (request.args.get("yUnit") or "").strip()
        subplot_types = [value.strip().lower() for value in request.args.getlist("plotType") if value is not None]
        subplot_colors = [value.strip().lower() for value in request.args.getlist("color") if value is not None]
        inverted_bars = [value.strip().lower() for value in request.args.getlist("invertBar") if value is not None]
        animation_speed_raw = (request.args.get("animationSpeed") or "0.1").strip()
        max_points_raw = (request.args.get("maxPoints") or "").strip()
        renderer = (request.args.get("renderer") or "auto").strip().lower()
        size = (request.args.get("size") or "m").strip().lower()
        animate = (request.args.get("animate") or "false").lower() in {"1", "true", "yes"}

        refresh_graph_cache_for_signature(graph_tour_name)

        try:
            animation_speed = float(animation_speed_raw)
        except ValueError:
            return jsonify({"error": "animationSpeed must be a positive number."}), 400
        if animation_speed <= 0:
            return jsonify({"error": "animationSpeed must be greater than zero."}), 400

        if max_points_raw:
            try:
                max_points = int(max_points_raw)
            except ValueError:
                return jsonify({"error": "maxPoints must be an integer greater than 10."}), 400
            if max_points != 0 and max_points < 10:
                return jsonify({"error": "maxPoints must be an integer greater than 10."}), 400
        else:
            max_points = GRAPH_PREVIEW_MAX_POINTS_DEFAULT

        if subplots_raw:
            try:
                subplot_count = int(subplots_raw)
            except ValueError:
                return jsonify({"error": "subplots must be an integer between 1 and 3."}), 400
            if subplot_count < 1 or subplot_count > 3:
                return jsonify({"error": "subplots must be between 1 and 3."}), 400
            if len(y_cols) != subplot_count:
                return jsonify({"error": "Number of y columns must match subplot count."}), 400
            if subplot_types and len(subplot_types) != subplot_count:
                return jsonify({"error": "Number of plotType values must match subplot count."}), 400
            if subplot_colors and len(subplot_colors) != subplot_count:
                return jsonify({"error": "Number of color values must match subplot count."}), 400
            if inverted_bars and len(inverted_bars) != subplot_count:
                return jsonify({"error": "Number of invertBar values must match subplot count."}), 400

        try:
            graph_result = generate_graph_asset_with_info(
                csv_name,
                x_col,
                y_cols,
                animate,
                y_label=y_label,
                y_unit=y_unit,
                subplot_types=subplot_types,
                subplot_colors=subplot_colors,
                inverted_bars=inverted_bars,
                animation_speed=animation_speed,
                renderer=renderer,
                size=size,
                tour_name=graph_tour_name,
                max_points=max_points,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": f"Graph generation failed: {exc}"}), 500

        return jsonify(
            {
                "ok": True,
                "path": f"/graphs/{graph_tour_name}/{graph_result['filename']}",
                "animated": animate,
                "tour": graph_tour_name,
                "sampled": graph_result["sampled"],
                "originalPoints": graph_result["originalPoints"],
                "plottedPoints": graph_result["plottedPoints"],
            }
        )

    @app.get("/api/viewer/graph")
    def get_graph_for_viewer():
        """Generate and return URL for graph image in read-only viewer for a selected tour."""
        tour_name_raw = (request.args.get("name") or "").strip()
        if not tour_name_raw:
            return jsonify({"error": "name query parameter is required."}), 400
        tour_name = normalize_tour_name(tour_name_raw)

        csv_name = (request.args.get("csv") or "").strip()
        x_col = (request.args.get("x") or "").strip()
        y_cols = [value.strip() for value in request.args.getlist("y") if value and value.strip()]
        if not y_cols:
            legacy_y = (request.args.get("y") or "").strip()
            if legacy_y:
                y_cols = [legacy_y]
        subplots_raw = (request.args.get("subplots") or "").strip()
        y_label = (request.args.get("yLabel") or "").strip()
        y_unit = (request.args.get("yUnit") or "").strip()
        subplot_types = [value.strip().lower() for value in request.args.getlist("plotType") if value is not None]
        subplot_colors = [value.strip().lower() for value in request.args.getlist("color") if value is not None]
        inverted_bars = [value.strip().lower() for value in request.args.getlist("invertBar") if value is not None]
        animation_speed_raw = (request.args.get("animationSpeed") or "0.1").strip()
        max_points_raw = (request.args.get("maxPoints") or "").strip()
        renderer = (request.args.get("renderer") or "auto").strip().lower()
        size = (request.args.get("size") or "m").strip().lower()
        animate = (request.args.get("animate") or "false").lower() in {"1", "true", "yes"}

        refresh_graph_cache_for_signature(tour_name)

        try:
            animation_speed = float(animation_speed_raw)
        except ValueError:
            return jsonify({"error": "animationSpeed must be a positive number."}), 400
        if animation_speed <= 0:
            return jsonify({"error": "animationSpeed must be greater than zero."}), 400

        if max_points_raw:
            try:
                max_points = int(max_points_raw)
            except ValueError:
                return jsonify({"error": "maxPoints must be an integer greater than 10."}), 400
            if max_points != 0 and max_points < 10:
                return jsonify({"error": "maxPoints must be an integer greater than 10."}), 400
        else:
            max_points = GRAPH_PREVIEW_MAX_POINTS_DEFAULT

        if subplots_raw:
            try:
                subplot_count = int(subplots_raw)
            except ValueError:
                return jsonify({"error": "subplots must be an integer between 1 and 3."}), 400
            if subplot_count < 1 or subplot_count > 3:
                return jsonify({"error": "subplots must be between 1 and 3."}), 400
            if len(y_cols) != subplot_count:
                return jsonify({"error": "Number of y columns must match subplot count."}), 400
            if subplot_types and len(subplot_types) != subplot_count:
                return jsonify({"error": "Number of plotType values must match subplot count."}), 400
            if subplot_colors and len(subplot_colors) != subplot_count:
                return jsonify({"error": "Number of color values must match subplot count."}), 400
            if inverted_bars and len(inverted_bars) != subplot_count:
                return jsonify({"error": "Number of invertBar values must match subplot count."}), 400

        try:
            graph_result = generate_graph_asset_with_info(
                csv_name,
                x_col,
                y_cols,
                animate,
                y_label=y_label,
                y_unit=y_unit,
                subplot_types=subplot_types,
                subplot_colors=subplot_colors,
                inverted_bars=inverted_bars,
                animation_speed=animation_speed,
                renderer=renderer,
                size=size,
                tour_name=tour_name,
                max_points=max_points,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": f"Graph generation failed: {exc}"}), 500

        return jsonify(
            {
                "ok": True,
                "path": f"/graphs/{tour_name}/{graph_result['filename']}",
                "animated": animate,
                "tour": tour_name,
                "sampled": graph_result["sampled"],
                "originalPoints": graph_result["originalPoints"],
                "plottedPoints": graph_result["plottedPoints"],
            }
        )

    @app.get("/images360/<path:filename>")
    def get_panorama_image(filename: str):
        """Serve 360 panorama image files from static 360 image directory."""
        return send_from_directory(IMAGES_360_DIR, filename)

    @app.get("/images2d/<path:filename>")
    def get_2d_image(filename: str):
        """Serve 2D image files from static 2D image directory."""
        return send_from_directory(IMAGES_2D_DIR, filename)

    @app.get("/images/<path:filename>")
    def get_image_legacy(filename: str):
        """Legacy image route: attempt 360 first, then 2D."""
        panorama_candidate = IMAGES_360_DIR / filename
        if panorama_candidate.exists() and panorama_candidate.is_file():
            return send_from_directory(IMAGES_360_DIR, filename)

        image_2d_candidate = IMAGES_2D_DIR / filename
        if image_2d_candidate.exists() and image_2d_candidate.is_file():
            return send_from_directory(IMAGES_2D_DIR, filename)

        legacy_candidate = LEGACY_IMAGES_DIR / filename
        if legacy_candidate.exists() and legacy_candidate.is_file():
            return send_from_directory(LEGACY_IMAGES_DIR, filename)

        return jsonify({"error": "Image not found."}), 404

    @app.get("/graphs/<path:filename>")
    def get_graph_image(filename: str):
        """Serve generated graph image files from graph directory."""
        return send_from_directory(GRAPHS_DIR, filename)
