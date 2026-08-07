"""Export saved tours to a static GitHub Pages bundle.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from typing import Callable

from panocore.graph.service import generate_graph_asset
from panocore.settings import LEGACY_IMAGES_DIR
from panocore.storage import (
    graph_dir_for_tour,
    image_2d_dir_for_tour,
    load_tour,
    normalize_tour_name,
    panorama_dir_for_tour,
)

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
PAGES_DIR = PROJECT_ROOT / "gh-pages"
PUBLISHED_DIR = PAGES_DIR / "published"
TOURS_DIR = PUBLISHED_DIR / "tours"

ProgressCallback = Callable[[int, str], None]


def _emit_progress(progress: ProgressCallback | None, percent: int, message: str) -> None:
    if progress is None:
        return
    progress(max(0, min(100, int(percent))), message)


def _normalize_github_token(token: str) -> str:
    """Normalize pasted token text (supports optional Bearer/token prefixes)."""
    text = str(token or "").strip()
    lower = text.lower()
    if lower.startswith("bearer "):
        return text[7:].strip()
    if lower.startswith("token "):
        return text[6:].strip()
    return text


def _extract_filename(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    path_only = urlparse(raw).path
    return Path(path_only).name


def _find_first_existing(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _copy_required_file(src: Path | None, dst: Path, what: str) -> None:
    if src is None:
        raise FileNotFoundError(f"Missing required {what} file for static export.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _resolve_panorama_source(tour_name: str, scene_panorama: str) -> tuple[Path, str]:
    filename = _extract_filename(scene_panorama)
    if not filename:
        raise FileNotFoundError("Scene panorama path is empty.")

    src = _find_first_existing(
        [
            panorama_dir_for_tour(tour_name) / filename,
            LEGACY_IMAGES_DIR / normalize_tour_name(tour_name) / filename,
            LEGACY_IMAGES_DIR / filename,
        ]
    )
    if src is None:
        raise FileNotFoundError(f"Could not locate panorama '{filename}' for tour '{tour_name}'.")
    return src, filename


def _resolve_2d_source(tour_name: str, image_block: dict) -> tuple[Path, str]:
    filename = _extract_filename(image_block.get("file") or image_block.get("path"))
    if not filename:
        raise FileNotFoundError("Image hotspot has no file/path configured.")

    src = _find_first_existing([image_2d_dir_for_tour(tour_name) / filename])
    if src is None:
        raise FileNotFoundError(f"Could not locate 2D image '{filename}' for tour '{tour_name}'.")
    return src, filename


def _build_graph_for_hotspot(tour_name: str, graph_block: dict) -> str:
    csv_name = str(graph_block.get("csv") or "").strip()
    if not csv_name:
        raise ValueError("Graph hotspot is missing csv field.")

    y_cols = graph_block.get("yColumns")
    if not isinstance(y_cols, list) or not y_cols:
        legacy_y = str(graph_block.get("y") or "").strip()
        y_cols = [legacy_y] if legacy_y else []

    if not y_cols:
        raise ValueError("Graph hotspot must define y or yColumns.")

    graph_filename = generate_graph_asset(
        csv_name=csv_name,
        x_col=str(graph_block.get("x") or "").strip(),
        y_cols=y_cols,
        animate=bool(graph_block.get("animate") is True or str(graph_block.get("animate", "")).lower() == "true"),
        y_label=str(graph_block.get("yLabel") or "").strip() or None,
        y_unit=str(graph_block.get("yUnit") or "").strip() or None,
        subplot_types=graph_block.get("subplotTypes") if isinstance(graph_block.get("subplotTypes"), list) else None,
        subplot_colors=graph_block.get("subplotColors") if isinstance(graph_block.get("subplotColors"), list) else None,
        inverted_bars=graph_block.get("invertedBars") if isinstance(graph_block.get("invertedBars"), list) else None,
        animation_speed=graph_block.get("animationSpeed", 0.1),
        renderer=str(graph_block.get("renderer") or "auto"),
        size="m",
        tour_name=tour_name,
        max_points=0,
        max_animation_frames=60,
        animation_loop_count=3,
        animation_time_budget_seconds=15.0,
        force_regenerate=True,
    )
    return graph_filename


def _export_tour(tour_name: str, progress: ProgressCallback | None = None) -> str:
    normalized = normalize_tour_name(tour_name)
    source_tour = load_tour(normalized)
    tour_payload = copy.deepcopy(source_tour)

    target_tour_dir = TOURS_DIR / normalized
    target_panorama_dir = target_tour_dir / "images360"
    target_image_dir = target_tour_dir / "images2d"
    target_graph_dir = target_tour_dir / "graphs"

    target_tour_dir.mkdir(parents=True, exist_ok=True)
    target_panorama_dir.mkdir(parents=True, exist_ok=True)
    target_image_dir.mkdir(parents=True, exist_ok=True)
    target_graph_dir.mkdir(parents=True, exist_ok=True)

    scenes = tour_payload.get("scenes", {})
    if not isinstance(scenes, dict):
        raise ValueError(f"Tour '{normalized}' has invalid scenes payload.")

    scene_items = list(scenes.items())
    total_steps = 1  # final manifest/json write step
    for _, scene in scene_items:
        if isinstance(scene, dict):
            total_steps += 1  # panorama copy
            for spot in scene.get("hotSpots", []):
                if isinstance(spot, dict) and str(spot.get("kind") or "scene").strip().lower() in {"image", "graph"}:
                    total_steps += 1
    completed_steps = 0

    def _step(message: str) -> None:
        nonlocal completed_steps
        completed_steps += 1
        _emit_progress(progress, round((completed_steps / total_steps) * 100), message)

    _emit_progress(progress, 0, f"Preparing tour {normalized}...")

    for scene_id, scene in scene_items:
        if not isinstance(scene, dict):
            raise ValueError(f"Scene '{scene_id}' in tour '{normalized}' is invalid.")

        src_panorama, panorama_name = _resolve_panorama_source(normalized, str(scene.get("panorama") or ""))
        dst_panorama = target_panorama_dir / panorama_name
        _copy_required_file(src_panorama, dst_panorama, "panorama")
        scene["panorama"] = f"published/tours/{normalized}/images360/{panorama_name}"
        _step(f"Copied panorama for {scene_id}.")

        hot_spots = scene.get("hotSpots", [])
        if not isinstance(hot_spots, list):
            raise ValueError(f"Scene '{scene_id}' in tour '{normalized}' has invalid hotSpots.")

        for spot in hot_spots:
            if not isinstance(spot, dict):
                continue
            kind = str(spot.get("kind") or "scene").strip().lower()

            if kind == "image":
                image_block = spot.get("image")
                if not isinstance(image_block, dict):
                    raise ValueError(f"Image hotspot in scene '{scene_id}' is missing image data.")
                src_image, image_name = _resolve_2d_source(normalized, image_block)
                dst_image = target_image_dir / image_name
                _copy_required_file(src_image, dst_image, "2D image")
                image_block["file"] = image_name
                image_block["path"] = f"published/tours/{normalized}/images2d/{image_name}"
                _step(f"Copied image hotspot for {scene_id}.")

            if kind == "graph":
                graph_block = spot.get("graph")
                if not isinstance(graph_block, dict):
                    raise ValueError(f"Graph hotspot in scene '{scene_id}' is missing graph data.")

                graph_name = _build_graph_for_hotspot(normalized, graph_block)
                src_graph = graph_dir_for_tour(normalized) / graph_name
                dst_graph = target_graph_dir / graph_name
                _copy_required_file(src_graph, dst_graph, "graph")
                graph_block["path"] = f"published/tours/{normalized}/graphs/{graph_name}"
                _step(f"Copied graph hotspot for {scene_id}.")

    with (target_tour_dir / "tour.json").open("w", encoding="utf-8") as handle:
        json.dump(tour_payload, handle, indent=2)

    _step(f"Wrote tour manifest for {normalized}.")
    _emit_progress(progress, 100, f"Tour {normalized} exported.")

    return normalized


def _read_existing_manifest_tours() -> list[str]:
    manifest_path = PUBLISHED_DIR / "tours.json"
    if not manifest_path.exists():
        return []

    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(payload, dict):
        return []
    tours = payload.get("tours")
    if not isinstance(tours, list):
        return []
    return [str(name).strip() for name in tours if str(name).strip()]


def _write_manifest(tours: list[str], *, merge_existing: bool = True) -> None:
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)
    merged = set(tours)
    if merge_existing:
        merged.update(_read_existing_manifest_tours())

    manifest = {
        "tours": sorted(merged),
    }
    with (PUBLISHED_DIR / "tours.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)


def export_pages(tours: list[str], *, merge_existing: bool = True, progress: ProgressCallback | None = None) -> list[str]:
    if not tours:
        return []

    TOURS_DIR.mkdir(parents=True, exist_ok=True)

    exported: list[str] = []
    total_tours = len(tours)
    for idx, tour_name in enumerate(tours):
        tour_base = round((idx / total_tours) * 100) if total_tours else 0
        tour_span = round((1 / total_tours) * 100) if total_tours else 100

        def _tour_progress(percent: int, message: str) -> None:
            _emit_progress(progress, tour_base + round((percent / 100) * tour_span), message)

        normalized = _export_tour(tour_name, progress=_tour_progress)
        exported.append(normalized)

    _write_manifest(exported, merge_existing=merge_existing)
    _emit_progress(progress, 100, "Static tour manifest updated.")
    return exported


def _run_checked(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


def _github_request(method: str, url: str, token: str, payload: dict | None = None) -> tuple[int, dict | None]:
    normalized_token = _normalize_github_token(token)
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = Request(url=url, method=method, data=data)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {normalized_token}")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if payload is not None:
        request.add_header("Content-Type", "application/json")

    try:
        with urlopen(request) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        parsed = None
        if body:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {"message": body}
        return exc.code, parsed


def _ensure_remote_repo(owner: str, repo: str, token: str, private: bool, as_org: bool) -> None:
    check_url = f"https://api.github.com/repos/{owner}/{repo}"
    status, _ = _github_request("GET", check_url, token)
    if status == 200:
        return
    if status == 401:
        raise RuntimeError(
            "GitHub authentication failed (HTTP 401). Check that the token is valid, not expired, and pasted without extra characters."
        )
    if status != 404:
        raise RuntimeError(f"Failed checking repository {owner}/{repo}. HTTP {status}.")

    create_payload = {
        "name": repo,
        "private": private,
        "description": "Static PanoCoTA tour package",
        "auto_init": False,
    }

    if as_org:
        create_url = f"https://api.github.com/orgs/{owner}/repos"
    else:
        create_url = "https://api.github.com/user/repos"

    create_status, create_body = _github_request("POST", create_url, token, create_payload)
    if create_status not in {200, 201}:
        message = ""
        if isinstance(create_body, dict):
            message = str(create_body.get("message") or "")
        raise RuntimeError(f"Failed creating repository {owner}/{repo}. HTTP {create_status}. {message}")


def _publish_bundle_to_repo(owner: str, repo: str, token: str, branch: str, commit_message: str) -> None:
    normalized_token = _normalize_github_token(token)
    if not PAGES_DIR.exists():
        raise FileNotFoundError("gh-pages folder does not exist. Run export first.")
    if not (PAGES_DIR / "index.html").exists():
        raise FileNotFoundError("gh-pages/index.html is missing. Static Pages bundle must include a root index.html.")

    with tempfile.TemporaryDirectory(prefix="panocota-pages-") as temp_dir:
        temp_path = Path(temp_dir)
        shutil.copytree(PAGES_DIR, temp_path / "site", dirs_exist_ok=True)
        site_dir = temp_path / "site"

        _run_checked(["git", "init"], cwd=site_dir)
        _run_checked(["git", "checkout", "-B", branch], cwd=site_dir)
        _run_checked(["git", "config", "user.name", "PanoCoTA Export Bot"], cwd=site_dir)
        _run_checked(["git", "config", "user.email", "panocota-export-bot@users.noreply.github.com"], cwd=site_dir)

        remote_url = f"https://x-access-token:{normalized_token}@github.com/{owner}/{repo}.git"
        _run_checked(["git", "remote", "add", "origin", remote_url], cwd=site_dir)
        _run_checked(["git", "add", "."], cwd=site_dir)
        _run_checked(["git", "commit", "-m", commit_message, "--allow-empty"], cwd=site_dir)
        _run_checked(["git", "push", "--force", "origin", branch], cwd=site_dir)


def _configure_pages_branch_source(owner: str, repo: str, token: str, branch: str) -> tuple[str | None, str | None]:
    """Enable GitHub Pages using branch/root source so no Actions runner is required."""
    payload = {
        "source": {
            "branch": branch,
            "path": "/",
        },
        "build_type": "legacy",
    }

    def _permission_warning(status_code: int, message: str) -> str:
        if status_code == 403 and "resource not accessible by personal access token" in message.lower():
            return (
                "Static package was pushed successfully, but this token cannot configure GitHub Pages automatically. "
                "Use a token with repository Administration (write) and Pages (write) permissions, or enable Pages manually "
                f"in repository settings: source branch '{branch}', folder '/'."
            )
        return (
            "Static package pushed, but GitHub Pages source could not be configured automatically "
            f"(HTTP {status_code}). {message}".strip()
        )

    create_url = f"https://api.github.com/repos/{owner}/{repo}/pages"
    status, body = _github_request("POST", create_url, token, payload)

    if status in {200, 201}:
        pages_url = None
        if isinstance(body, dict):
            pages_url = str(body.get("html_url") or "").strip() or None
        return pages_url, None

    # Already configured: attempt update to ensure branch/path are correct.
    if status in {409, 422}:
        update_url = f"https://api.github.com/repos/{owner}/{repo}/pages"
        update_status, update_body = _github_request("PUT", update_url, token, payload)
        if update_status in {200, 201, 204}:
            pages_url = f"https://{owner}.github.io/{repo}/"
            if isinstance(update_body, dict):
                pages_url = str(update_body.get("html_url") or pages_url).strip() or pages_url
            return pages_url, None

        message = ""
        if isinstance(update_body, dict):
            message = str(update_body.get("message") or "").strip()
        return None, _permission_warning(update_status, message)

    message = ""
    if isinstance(body, dict):
        message = str(body.get("message") or "").strip()
    return None, _permission_warning(status, message)


def _default_repo_name(exported_tours: list[str]) -> str:
    if len(exported_tours) == 1:
        return f"panocota-tour-{exported_tours[0]}"
    return "panocota-tours"


def default_repo_name(exported_tours: list[str]) -> str:
    """Return default repository name for exported tour set."""
    return _default_repo_name(exported_tours)


def ensure_remote_repo(owner: str, repo: str, token: str, private: bool, as_org: bool) -> None:
    """Ensure target GitHub repository exists (create when missing)."""
    _ensure_remote_repo(owner, repo, token, private=private, as_org=as_org)


def publish_bundle_to_repo(owner: str, repo: str, token: str, branch: str, commit_message: str) -> None:
    """Push local gh-pages static bundle to target GitHub repository branch."""
    _publish_bundle_to_repo(owner, repo, token, branch=branch, commit_message=commit_message)


def export_and_publish(
    tours: list[str],
    owner: str,
    token: str,
    repo: str = "",
    branch: str = "main",
    commit_message: str = "Publish static PanoCoTA tour package",
    private_repo: bool = False,
    github_org: bool = False,
    progress: ProgressCallback | None = None,
) -> tuple[list[str], str, str | None, str | None]:
    """Export tours, push static bundle, and configure Pages branch deployment."""
    _emit_progress(progress, 1, "Exporting static tour bundle...")
    exported = export_pages(tours, merge_existing=True, progress=lambda pct, msg: _emit_progress(progress, round(pct * 0.70), msg))
    if not exported:
        raise RuntimeError("No tours were exported.")

    repo_name = (repo or "").strip() or _default_repo_name(exported)
    _emit_progress(progress, 72, "Ensuring GitHub repository exists...")
    _ensure_remote_repo(owner, repo_name, token, private=private_repo, as_org=github_org)
    _emit_progress(progress, 85, "Pushing static bundle to GitHub...")
    _publish_bundle_to_repo(owner, repo_name, token, branch=branch, commit_message=commit_message)
    _emit_progress(progress, 95, "Configuring GitHub Pages...")
    pages_url, pages_warning = _configure_pages_branch_source(owner, repo_name, token, branch)
    _emit_progress(progress, 100, "Publish complete.")
    return exported, repo_name, pages_url, pages_warning


if __name__ == "__main__":
    raise SystemExit(
        "This module is editor-driven only. Use the 'Publish To GitHub' section in the PanoCoTA editor UI."
    )
