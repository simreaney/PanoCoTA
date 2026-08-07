<img src="static/branding/panocota_logo.png" alt="PanoCoTA logo" width="220" align="left" />

<br clear="left" />

# PanoCoTA (*Pano*ramic *Co*ntent and *T*ours for *A*cademia)

PanoCoTA is a web app for creating interactive 360 tours that include (animated) graphed data, 2D images and free text to aid scientific communication.

This README is a practical step-by-step guide for first use.

## What It Does

- Builds 360 tours from panorama scenes.
- Lets you add four hotspot types: Scene Navigation, Graphed Data, Image, and Free Text.
- Supports CSV-driven graph hotspots with up to 3 subplots.
- Saves tours so they can be loaded and edited later.
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

3. Add hotspots
- In the Hotspots section, click Add Hotspot.
- Choose Hotspot Type and enter hotspot Title.
- For graph hotspots, choose subplot type/color/invert options as needed.
- Click Place Hotspot In Viewer, then click once in the panorama to place it.

Hotspot types:
- Scene Navigation: choose Target Scene.
- Graphed Data: upload/select CSV, choose x/y columns, subplot types, subplot colors, and optional Y-axis inversion.
- Image: upload/select a 2D image, then add.
- Free Text: enter Free Text Content, then add.

Hotspot editing modes:
- Move Hotspots: left-drag an existing hotspot to reposition it.
- Delete Hotspots: click an existing hotspot to remove it.

4. Save your tour
- In Save Tour, choose an existing tour name or create a new one.
- Click Save Tour To Disk.

5. Load it later
- In Load Tour, select a saved tour and click Load Tour From Disk.

## Demo Tour Instructions

The bundled demo tour is saved at `static/tours/demo.json` and is meant to be used as a ready-made example.

1. Start the app.
- Run `python panocota.py`.
- Leave the app open so the viewer and editor can load the demo tour.

2. Open the read-only viewer first.
- Go to `http://127.0.0.1:5000/viewer`.
- Load `demo` there to inspect the finished tour without editing it.

3. Then open the editor if you want to work with the demo.
- Go to `http://127.0.0.1:5000`.
- In Load Tour, select `demo` and click Load Tour From Disk.

4. Explore the sample hotspots.
- Scene hotspots move between Gladi Grassland and Gladi Dairy.
- Graph hotspots open hover cards with plotted data.
- Image hotspots show 2D reference panels.
- Text Link hotspots open external research links.

5. Use the demo as a template.
- Save under a new tour name before making changes.
- Keep `demo` around if you want a clean sample tour for testing publish and viewer behavior.

## Notes

- Panorama and 2D images are stored separately per tour.
- Click the sidebar logo to open a larger popup preview of the logo.
- Graph hotspots can be static or animated.
- Graph hotspot animation timing is automatic in the UI and API defaults: target 0.1s per frame, then adjusted to keep one loop between 5s and 10s.
- Graph preview may downsample large datasets in-editor for responsiveness; exported graphs include full datasets.
- Graph floating windows use a fixed width for all subplot counts; 3-subplot graphs can scroll vertically when taller than the viewport.
- Graph cache persists across closing/reopening tours and is auto-cleared only when graph renderer/settings signatures change.
- Tests are not included yet and will be added later.

## Publish To GitHub Pages

This repository now includes a static publishing pipeline for tours.

1. Build your tour locally in the editor and save it.

2. In the editor, scroll to the Publish To GitHub section at the bottom.

3. Choose publish options:
- Publish Scope: Current Tour or All Saved Tours
- GitHub Owner and optional Repo
- Owner Type, Branch, and private repo toggle
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

- Aaron Neill
- GitHub Copilot
