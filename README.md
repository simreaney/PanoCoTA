<img src="static/branding/panocota_logo.png" alt="PanoCoTA logo" width="220" align="left" />

<br clear="left" />

# PanoCoTA (*Pano*ramic *Co*ntent and *T*ours for *A*cademia)

Conceptualised and vibe-coded by A J Neill (JLU Giessen)

[![DOI](https://zenodo.org/badge/1325412562.svg)](https://doi.org/10.5281/zenodo.21840893)

PanoCoTA is a web app for creating interactive 360 tours that include (animated) graphed data, 2D images and free text to aid scientific communication.

This README is a practical step-by-step guide for first use.

## What It Does

- Builds 360 tours from panorama scenes (full-sphere or partial/cylinder coverage).
- Lets you add hotspot types: Scene Navigation, Graphed Data, Image, Free Text, Web Link, and always-visible Text Panels.
- Supports CSV-driven graph hotspots with up to 8 stacked subplots (Line, Scatter, or Bar per subplot).
- Graph subplots can share one X column or each use its own X column (e.g. two sites with different timestamps on a common time axis).
- Any subplot can share its Y-axis range with another subplot for direct comparison.
- Add, move, delete, and edit hotspots (including changing the columns a graph subplot plots).
- Image hotspots support an optional caption displayed below the image.
- Web Link hotspots support opening in a new tab or the same tab.
- Scene management: switch the active scene, jump to a scene, or delete a scene.
- Panorama coverage: auto-detect vertical FOV and offset from image metadata, or set them manually for partial (cylinder) panoramas.
- Saves tours so they can be loaded, closed, deleted, and edited later.
- Built-in Tour Help popup with step-by-step guidance.
- Exports and publishes static, hostable tour packages to GitHub from the editor UI.

## Setup

1. Clone the repository and open the project folder.

2. Create and activate a virtual environment.

Use Python 3.13.x for the virtual environment. Python 3.14 is not supported yet.

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Install dependencies.

```bash
pip install -r requirements.txt
```

4. Start the app.

```bash
python panocota.py
```

This starts in quiet mode by default (reduced console output, debug/reloader off).

Optional environment flags:

- `PANOCOTA_DEBUG=1` enables Flask debug mode.
- `PANOCOTA_RELOAD=1` enables auto-reload.
- `PANOCOTA_VERBOSE=1` enables verbose request/startup logging.

5. Open the UI.

For tour editing: http://127.0.0.1:5000

For a read-only viewer: http://127.0.0.1:5000/viewer

## Step-by-Step: Build Your First Tour

1. Upload a 360 image
- In Add Scene, use the image upload control and upload your panorama.
- After upload, pick that image in the 360 Panorama Image dropdown.

2. Create a scene
- In Add Scene, enter a Title.
- Click Add Scene.
- Note: the scene Title is also used as the scene ID.
- Panorama Coverage: leave as Full sphere (360 x 180) for standard equirectangular panoramas. If your image is a partial panorama (360 sweep missing sky or ground), switch to Partial (360 x limited vertical) and either click Detect Coverage From Image to read the vertical FOV/offset from the image (metadata or aspect-ratio estimate), or enter the Vertical Field Of View and Vertical Offset manually.

3. Add hotspots
- In the Hotspots section, click Add Hotspot.
- Choose Hotspot Type and enter hotspot Title.
- For graph hotspots, choose subplot type/color/invert options as needed.
- Click Place Hotspot In Viewer, then click once in the panorama to place it.

Hotspot types:
- Scene Navigation: choose Target Scene.
- Graphed Data: upload/select CSV, choose the X column, then per subplot set the Y column, plot type (Line, Scatter, or Bar), color, optional Y-axis label, optional Y-axis inversion, and optional "Share Y range with" another subplot. The X column can be shared by all subplots or set to "(per-subplot X)" so each subplot uses its own timestamp column (useful for plotting several sites with different timestamps on one common time axis).
- Image: upload/select a 2D image, optionally add a caption shown below the image, then add.
- Free Text: enter Free Text Content, then add.
- Text Panel: enter text that stays visible at all times (no hover) — good for scene introductions.
- Web Link: enter Free Text Content plus an external URL and click behavior (open in new tab or same tab).

Hotspot editing modes:
- Move Hotspots: left-drag an existing hotspot to reposition it.
- Delete Hotspots: click an existing hotspot to remove it.
- Edit Hotspot: click an existing hotspot to load it into the form, change any setting (including the columns a graph subplot plots), then Save Changes.

4. Manage scenes
- Use the Active Scene dropdown plus Open Scene to jump between scenes while editing.
- Use Delete Scene to remove a scene from the tour (remember to save afterwards).

5. Save your tour
- In Save Tour, choose an existing tour name or create a new one.
- Click Save Tour To Disk.

6. Load it later
- In Load Tour, select a saved tour and click Load Tour From Disk.
- Use Close Tour to drop the current tour without saving, or Delete Tour to remove a saved tour from disk.
- Stuck? Click Open Tour Help in the Current Tour section for a step-by-step popup guide.

## Notes

- Panorama and 2D images are stored separately per tour.
- Click the sidebar logo to open a larger popup preview of the logo.
- Graph hotspots can be static or animated.
- Graph hotspot animation timing is automatic in the UI and API defaults: target 0.1s per frame, then adjusted to keep one loop between 5s and 10s.
- Graph preview may downsample large datasets in-editor for responsiveness; exported graphs include full datasets.
- Graph floating windows use a fixed width for all subplot counts; tall multi-subplot graphs can scroll vertically when taller than the viewport.
- Graph cache persists across closing/reopening tours and is auto-cleared only when graph renderer/settings signatures change.
- Graph subplots render with a tight layout and right-aligned Y-axis labels so stacked subplots line up vertically.
- Non-finite CSV values (NaN/inf) are skipped so they cannot break axis limits.
- Tests live in `tests/` and can be run with `python -m pytest tests/`.

## Publish To GitHub Pages

This repository now includes a static publishing pipeline for tours.

1. Build your tour locally in the editor and save it.

2. In the editor, scroll to the Publish To GitHub section at the bottom.

3. Choose publish options:
- Publish Scope: Current Tour or All Saved Tours
- GitHub Owner and optional Repo
- Owner Type, Branch, and private repo toggle
- Publish via GitHub Pages (checked by default; uncheck to push the static package without configuring Pages)
- GitHub Token (one-time)

4. Click Export and Publish.

Warning: exported GitHub Pages bundles can still hit file size limits if stale or oversized generated assets remain in the export path. This is being addressed, and the publish flow now tries to block that failure mode before the push.

### Personal Access Token (PAT) Permissions

PanoCoTA uses the GitHub API plus a git push to publish, so your token must allow:

- Repository contents write access (push branch updates).
- Repository administration write access (set Pages source branch/path).
- GitHub Pages write access (create/update Pages configuration).
- Repository metadata read access (repository checks).

If PanoCoTA needs to create a new repository for you, the token also needs repository creation rights for that owner.

Recommended options:

- Classic PAT: `repo` scope is the simplest option and covers publish operations.
- Fine-grained PAT: grant repository permissions for Contents (Read and write), Administration (Read and write), Pages (Read and write), and Metadata (Read-only), plus repository creation permission if you want auto-create behavior.

If your org restricts token permissions, pre-create the target repository and then publish into that existing repo.

Exports are merged into the existing published tour manifest by default, so publishing a new tour does not remove previously published tours from the viewer list.

5. The export writes a hostable site into the gh-pages folder:
- gh-pages/index.html
- gh-pages/viewer.js
- gh-pages/viewer.css
- gh-pages/branding/panocota_logo.png
- gh-pages/published/tours.json
- gh-pages/published/tours/<tour_name>/...

6. Publishing from the editor will:
- create the target repository if it does not exist
- push the static package to the target branch (default main)

By default, repo name is auto-generated:
- one tour: panocota-tour-<tour_name>
- multiple tours: panocota-tours

7. The publish step also attempts to configure GitHub Pages automatically to serve from the pushed branch root (`/`). 

8. If Pages could not be configured automatically, open the target repository settings and set GitHub Pages source to the pushed branch root.

## Viewer Modes

PanoCoTA has two viewer contexts: the local read-only viewer and the published GitHub Pages viewer.

Local viewer (`/viewer`):

- Loads tours from your saved local tours list.
- Shows the control panel with tour selection, refresh, and manual load actions.
- Uses hover cards for graph/image/text hotspots.

Published viewer (GitHub Pages root):

- Reads `published/tours.json` and loads tours from `published/tours/<tour_name>/tour.json`.
- Supports direct linking with `?tour=<tour_name>`.

Single-tour published mode:

- Automatically enabled when `published/tours.json` contains exactly one tour.
- Hides the sidebar controls and prioritizes the panorama canvas.
- Still loads the only published tour automatically.

Multi-tour published mode:

- Used when two or more tours are listed in `published/tours.json`.
- Shows the sidebar controls so users can switch between tours.
- Updates the URL query parameter (`?tour=...`) to reflect the currently loaded tour.

## License

GNU GPL v3.0. See LICENSE.

## Contributors

- Aaron J Neill
- GitHub Copilot
