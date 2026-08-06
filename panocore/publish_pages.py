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
PAGES_DIR = BASE_DIR / "gh-pages"
PUBLISHED_DIR = PAGES_DIR / "published"
TOURS_DIR = PUBLISHED_DIR / "tours"


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
        animation_speed=graph_block.get("animationSpeed", 1.0),
        renderer=str(graph_block.get("renderer") or "auto"),
        size=str(graph_block.get("size") or "m"),
        tour_name=tour_name,
    )
    return graph_filename


def _export_tour(tour_name: str) -> str:
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

    for scene_id, scene in scenes.items():
        if not isinstance(scene, dict):
            raise ValueError(f"Scene '{scene_id}' in tour '{normalized}' is invalid.")

        src_panorama, panorama_name = _resolve_panorama_source(normalized, str(scene.get("panorama") or ""))
        dst_panorama = target_panorama_dir / panorama_name
        _copy_required_file(src_panorama, dst_panorama, "panorama")
        scene["panorama"] = f"published/tours/{normalized}/images360/{panorama_name}"

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

            if kind == "graph":
                graph_block = spot.get("graph")
                if not isinstance(graph_block, dict):
                    raise ValueError(f"Graph hotspot in scene '{scene_id}' is missing graph data.")

                graph_name = _build_graph_for_hotspot(normalized, graph_block)
                src_graph = graph_dir_for_tour(normalized) / graph_name
                dst_graph = target_graph_dir / graph_name
                _copy_required_file(src_graph, dst_graph, "graph")
                graph_block["path"] = f"published/tours/{normalized}/graphs/{graph_name}"

    with (target_tour_dir / "tour.json").open("w", encoding="utf-8") as handle:
        json.dump(tour_payload, handle, indent=2)

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


def export_pages(tours: list[str], *, merge_existing: bool = True) -> list[str]:
    if not tours:
        return []

    TOURS_DIR.mkdir(parents=True, exist_ok=True)

    exported: list[str] = []
    for tour_name in tours:
        normalized = _export_tour(tour_name)
        exported.append(normalized)

    _write_manifest(exported, merge_existing=merge_existing)
    return exported


def _run_checked(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


def _github_request(method: str, url: str, token: str, payload: dict | None = None) -> tuple[int, dict | None]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = Request(url=url, method=method, data=data)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
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
    if not PAGES_DIR.exists():
        raise FileNotFoundError("gh-pages folder does not exist. Run export first.")

    with tempfile.TemporaryDirectory(prefix="panocota-pages-") as temp_dir:
        temp_path = Path(temp_dir)
        shutil.copytree(PAGES_DIR, temp_path / "site", dirs_exist_ok=True)
        site_dir = temp_path / "site"

        _run_checked(["git", "init"], cwd=site_dir)
        _run_checked(["git", "checkout", "-B", branch], cwd=site_dir)
        _run_checked(["git", "config", "user.name", "PanoCoTA Export Bot"], cwd=site_dir)
        _run_checked(["git", "config", "user.email", "panocota-export-bot@users.noreply.github.com"], cwd=site_dir)

        remote_url = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
        _run_checked(["git", "remote", "add", "origin", remote_url], cwd=site_dir)
        _run_checked(["git", "add", "."], cwd=site_dir)
        _run_checked(["git", "commit", "-m", commit_message, "--allow-empty"], cwd=site_dir)
        _run_checked(["git", "push", "--force", "origin", branch], cwd=site_dir)


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
) -> tuple[list[str], str]:
    """Export selected tours, ensure target repository, and publish static bundle."""
    exported = export_pages(tours, merge_existing=True)
    if not exported:
        raise RuntimeError("No tours were exported.")

    repo_name = (repo or "").strip() or _default_repo_name(exported)
    _ensure_remote_repo(owner, repo_name, token, private=private_repo, as_org=github_org)
    _publish_bundle_to_repo(owner, repo_name, token, branch=branch, commit_message=commit_message)
    return exported, repo_name


if __name__ == "__main__":
    raise SystemExit(
        "This module is editor-driven only. Use the 'Publish To GitHub' section in the PanoCoTA editor UI."
    )
