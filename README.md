# PanoCoTA (Panoramic Content and Tours for Academia)

PanoCoTA is a web app for creating interactive 360 tours for academic use.

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

Windows PowerShell:

```powershell
py -3 -m venv .venv
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
- Open Add Hotspot.
- Choose Source Scene.
- Set Pitch and Yaw, or click Use Current View.
- Enter hotspot Title.

Hotspot types:
- Scene Navigation: choose Target Scene.
- Graphed Data: upload/select CSV, choose columns, then add.
- Image: upload/select a 2D image, then add.
- Free Text: enter Free Text Content, then add.

4. Save your tour
- In Save Tour, choose an existing tour name or create a new one.
- Click Save Tour To Disk.

5. Load it later
- In Load Tour, select a saved tour and click Load Tour From Disk.

## Notes

- Panorama and 2D images are stored separately per tour.
- Graph hotspots can be static or animated.
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

7. Commit and push changes in this repo if you want to keep local export artifacts under version control. The included workflow .github/workflows/deploy-pages.yml deploys gh-pages/ to GitHub Pages for this repo.

8. In the target hosting repository settings, enable GitHub Pages for the pushed branch.

Viewer usage:
- Open your Pages URL root to load the viewer.
- Optional direct tour link: ?tour=<tour_name>

## License

MIT. See LICENSE.
