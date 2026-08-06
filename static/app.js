// Read This First:
// 1) boot() runs when this file loads in index.html.
// 2) loadTour() fetches current JSON from GET /api/tour.
// 3) fillSceneSelects() builds scene dropdowns from tour.scenes keys.
// 4) renderViewer() rebuilds Pannellum with converted scene config.
// 5) setupEvents() wires buttons for add scene/hotspot/upload/save.
// 6) "Use Current View" copies camera pitch/yaw into hotspot form.
// 7) "Add Hotspot" appends hotspot object to source scene in memory.
// 8) createHotspotDom() draws pulsing marker + hover card animation.
// 9) "Save Tour" POSTs full in-memory tour JSON to /api/tour.
// 10) Image uploads use /api/upload_360 for panoramas and /api/upload_2d for 2D hotspot images.

// Holds the active Pannellum viewer instance.
let viewer = null;

// Holds the in-memory tour object fetched from the backend.
let tour = null;
let csvFiles = [];
let csvColumns = [];
let availableTours = [];
let availablePanoramaImages = [];
let available2dImages = [];
let currentAssetTour = "tour";
let activeTourName = "";
const CREATE_NEW_TOUR_VALUE = "__create_new__";
let helpWindowRef = null;

// Cache all frequently used DOM nodes in one place.
const el = {
  sceneSelect: document.getElementById("scene-select"),
  jumpScene: document.getElementById("jump-scene"),
  deleteScene: document.getElementById("delete-scene"),
  addScene: document.getElementById("add-scene"),
  newSceneTitle: document.getElementById("new-scene-title"),
  newScenePanoramaSelect: document.getElementById("new-scene-panorama-select"),
  sceneUploadWrap: document.getElementById("scene-upload-wrap"),
  sceneImageUpload: document.getElementById("scene-image-upload"),
  uploadSceneImageButton: document.getElementById("upload-scene-image"),
  sceneImageResult: document.getElementById("scene-image-result"),
  hotspotKind: document.getElementById("hotspot-kind"),
  hotspotSource: document.getElementById("hotspot-source"),
  hotspotTarget: document.getElementById("hotspot-target"),
  hotspotPitch: document.getElementById("hotspot-pitch"),
  hotspotYaw: document.getElementById("hotspot-yaw"),
  hotspotLabel: document.getElementById("hotspot-label"),
  textContentWrap: document.getElementById("text-content-wrap"),
  hotspotFreeText: document.getElementById("hotspot-free-text"),
  hotspotCsv: document.getElementById("hotspot-csv"),
  hotspotX: document.getElementById("hotspot-x"),
  hotspotSubplots: document.getElementById("hotspot-subplots"),
  hotspotYSelects: document.getElementById("hotspot-y-selects"),
  hotspotAnimate: document.getElementById("hotspot-animate"),
  globalAnimationSpeed: document.getElementById("global-animation-speed"),
  hotspotImageFile: document.getElementById("hotspot-image-file"),
  imageCaptionWrap: document.getElementById("image-caption-wrap"),
  hotspotImageCaption: document.getElementById("hotspot-image-caption"),
  hotspotImageUpload: document.getElementById("hotspot-image-upload"),
  uploadHotspotImageButton: document.getElementById("upload-hotspot-image"),
  hotspotImageResult: document.getElementById("hotspot-image-result"),
  targetSceneWrap: document.getElementById("target-scene-wrap"),
  graphCsvWrap: document.getElementById("graph-csv-wrap"),
  graphXWrap: document.getElementById("graph-x-wrap"),
  graphSubplotsWrap: document.getElementById("graph-subplots-wrap"),
  graphYWrap: document.getElementById("graph-y-wrap"),
  graphAnimateWrap: document.getElementById("graph-animate-wrap"),
  graphAnimationSpeedWrap: document.getElementById("graph-animation-speed-wrap"),
  graphUploadWrap: document.getElementById("graph-upload-wrap"),
  imageFileWrap: document.getElementById("image-file-wrap"),
  imageUploadWrap: document.getElementById("image-upload-wrap"),
  captureView: document.getElementById("capture-view"),
  addHotspot: document.getElementById("add-hotspot"),
  saveTour: document.getElementById("save-tour"),
  loadTourButton: document.getElementById("load-tour"),
  closeTourButton: document.getElementById("close-tour"),
  helpToggleButton: document.getElementById("help-toggle"),
  deleteTourButton: document.getElementById("delete-tour"),
  currentTourName: document.getElementById("current-tour-name"),
  saveTourSelect: document.getElementById("save-tour-select"),
  saveTourNewNameWrap: document.getElementById("save-tour-new-name-wrap"),
  saveTourNewName: document.getElementById("save-tour-new-name"),
  publishScope: document.getElementById("publish-scope"),
  publishOwner: document.getElementById("publish-owner"),
  publishRepo: document.getElementById("publish-repo"),
  publishOwnerType: document.getElementById("publish-owner-type"),
  publishBranch: document.getElementById("publish-branch"),
  publishToken: document.getElementById("publish-token"),
  publishPrivate: document.getElementById("publish-private"),
  publishTourButton: document.getElementById("publish-tour"),
  publishResult: document.getElementById("publish-result"),
  status: document.getElementById("status"),
  csvUploadButton: document.getElementById("upload-csv-button"),
  csvUploadInput: document.getElementById("csv-upload"),
  csvUploadResult: document.getElementById("csv-upload-result"),
  tourSelect: document.getElementById("tour-select"),
  refreshTours: document.getElementById("refresh-tours"),
};

function resolveLoadTourName() {
  return el.tourSelect.value.trim();
}

function resolveSaveTourName() {
  const selected = (el.saveTourSelect?.value || "").trim();
  if (selected === CREATE_NEW_TOUR_VALUE) {
    return (el.saveTourNewName?.value || "").trim();
  }
  return selected;
}

function updateSaveTourUI() {
  const isCreateNew = (el.saveTourSelect?.value || "") === CREATE_NEW_TOUR_VALUE;
  el.saveTourNewNameWrap.classList.toggle("is-hidden", !isCreateNew);
}

function refreshSaveTourSelect(preferredName = "") {
  const options = [];
  const preferred = preferredName || activeTourName;

  if (preferred) {
    options.push({ value: preferred, label: `${preferred} (current)` });
  }

  availableTours.forEach((name) => {
    if (!name || name === preferred) {
      return;
    }
    options.push({ value: name, label: name });
  });

  options.push({ value: CREATE_NEW_TOUR_VALUE, label: "(create new tour)" });

  el.saveTourSelect.innerHTML = options
    .map((opt) => `<option value="${opt.value}">${opt.label}</option>`)
    .join("");

  if (preferred) {
    el.saveTourSelect.value = preferred;
  } else {
    el.saveTourSelect.value = CREATE_NEW_TOUR_VALUE;
  }
  updateSaveTourUI();
}

async function refreshTourList(preferredLoadName = "", preferredSaveName = "") {
  const response = await fetch("/api/tours");
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Failed to fetch tour list.");
  }

  availableTours = Array.isArray(body.tours) ? body.tours : [];
  setSelectOptions(el.tourSelect, availableTours, true, "(none saved yet)", preferredLoadName);
  refreshSaveTourSelect(preferredSaveName);
}

async function refreshImageList(preferredImage = "", preferredHotspotImage = "") {
  const [panoramaResponse, image2dResponse] = await Promise.all([
    fetch("/api/images_360"),
    fetch("/api/images_2d"),
  ]);
  const panoramaBody = await panoramaResponse.json();
  const image2dBody = await image2dResponse.json();
  if (!panoramaResponse.ok) {
    throw new Error(panoramaBody.error || "Failed to fetch 360 image list.");
  }
  if (!image2dResponse.ok) {
    throw new Error(image2dBody.error || "Failed to fetch 2D image list.");
  }

  currentAssetTour = panoramaBody.tour || image2dBody.tour || currentAssetTour;
  availablePanoramaImages = Array.isArray(panoramaBody.images) ? panoramaBody.images : [];
  available2dImages = Array.isArray(image2dBody.images) ? image2dBody.images : [];
  setSelectOptions(
    el.newScenePanoramaSelect,
    availablePanoramaImages,
    true,
    "(upload new image)",
    preferredImage,
  );
  setSelectOptions(
    el.hotspotImageFile,
    available2dImages,
    true,
    "(upload new image)",
    preferredHotspotImage || preferredImage,
  );
}

function setSelectOptions(selectEl, options, includeBlank = false, blankLabel = "", preferred = "") {
  const html = [];
  if (includeBlank) {
    html.push(`<option value="">${blankLabel}</option>`);
  }
  options.forEach((opt) => {
    html.push(`<option value="${opt}">${opt}</option>`);
  });
  selectEl.innerHTML = html.join("");

  if (preferred && options.includes(preferred)) {
    selectEl.value = preferred;
  } else if (includeBlank) {
    selectEl.value = "";
  } else if (options.length > 0) {
    selectEl.value = options[0];
  }
}

async function fetchCsvFiles() {
  const response = await fetch("/api/csvs");
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Failed to fetch CSV list.");
  }
  currentAssetTour = body.tour || currentAssetTour;
  return Array.isArray(body.files) ? body.files : [];
}

async function fetchCsvColumns(csvName) {
  if (!csvName) {
    return [];
  }

  const query = new URLSearchParams({ csv: csvName });
  const response = await fetch(`/api/csv_columns?${query.toString()}`);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Failed to fetch CSV columns.");
  }
  return Array.isArray(body.columns) ? body.columns : [];
}

function getSelectedSubplotConfigs() {
  const rows = Array.from(el.hotspotYSelects.querySelectorAll(".subplot-config-row"));
  return rows.map((row) => {
    const yNode = row.querySelector(".subplot-y-select");
    const typeNode = row.querySelector(".subplot-type-select");
    const invertNode = row.querySelector(".subplot-invert-check");
    return {
      y: (yNode?.value || "").trim(),
      type: (typeNode?.value || "line").trim().toLowerCase(),
      invertBar: Boolean(invertNode?.checked),
    };
  });
}

function getGlobalAnimationSpeed() {
  const raw = Number.parseFloat(el.globalAnimationSpeed?.value || "1");
  if (!Number.isFinite(raw)) {
    return 1;
  }
  return clamp(raw, 0.25, 4);
}

function updateInvertToggleVisibility() {
  const rows = Array.from(el.hotspotYSelects.querySelectorAll(".subplot-config-row"));
  rows.forEach((row) => {
    const typeNode = row.querySelector(".subplot-type-select");
    const invertLabel = row.querySelector(".subplot-invert-label");
    const invertNode = row.querySelector(".subplot-invert-check");
    const isBar = (typeNode?.value || "line") === "bar";
    if (invertLabel) {
      invertLabel.classList.toggle("is-hidden", !isBar);
    }
    if (!isBar && invertNode) {
      invertNode.checked = false;
    }
  });
}

function renderSubplotConfigRows(preferredConfigs = []) {
  const requested = Number.parseInt(el.hotspotSubplots.value, 10);
  const subplotCount = Number.isFinite(requested) ? clamp(requested, 1, 3) : 1;
  const html = [];

  for (let index = 0; index < subplotCount; index += 1) {
    const preferred = preferredConfigs[index] || {};
    const preferredType = ["line", "scatter", "bar"].includes(preferred.type)
      ? preferred.type
      : "line";
    html.push(
      `<div class="subplot-config-row">
        <label class="subplot-y-label">Subplot ${index + 1} Y Column<select class="subplot-y-select" id="hotspot-y-${index}"></select></label>
        <label class="subplot-type-label">Type<select class="subplot-type-select" id="hotspot-type-${index}">
          <option value="line" ${preferredType === "line" ? "selected" : ""}>Line</option>
          <option value="scatter" ${preferredType === "scatter" ? "selected" : ""}>Scatter</option>
          <option value="bar" ${preferredType === "bar" ? "selected" : ""}>Bar</option>
        </select></label>
        <label class="subplot-invert-label"><input class="subplot-invert-check" id="hotspot-invert-${index}" type="checkbox" ${preferred.invertBar ? "checked" : ""} /> Inverted bar</label>
      </div>`,
    );
  }
  el.hotspotYSelects.innerHTML = html.join("");

  const selects = Array.from(el.hotspotYSelects.querySelectorAll(".subplot-y-select"));
  selects.forEach((selectEl, index) => {
    const preferred = preferredConfigs[index]?.y || "";
    setSelectOptions(selectEl, csvColumns, false, "", preferred);
  });

  const typeSelects = Array.from(el.hotspotYSelects.querySelectorAll(".subplot-type-select"));
  typeSelects.forEach((selectEl) => {
    selectEl.addEventListener("change", updateInvertToggleVisibility);
  });
  updateInvertToggleVisibility();
}

async function refreshColumnSelects(preferredX = "", preferredConfigs = []) {
  const selectedCsv = el.hotspotCsv.value;
  csvColumns = await fetchCsvColumns(selectedCsv);

  setSelectOptions(el.hotspotX, csvColumns, true, "(auto index)", preferredX);
  renderSubplotConfigRows(preferredConfigs);
}

async function refreshCsvSelects(preferredCsv = "", preferredX = "", preferredConfigs = []) {
  csvFiles = await fetchCsvFiles();
  setSelectOptions(el.hotspotCsv, csvFiles, true, "(upload new csv)", preferredCsv);

  if (csvFiles.length === 0) {
    setSelectOptions(el.hotspotX, [], true, "(auto index)", "");
    csvColumns = [];
    renderSubplotConfigRows([]);
    return;
  }

  await refreshColumnSelects(preferredX, preferredConfigs);
}

async function loadTour() {
  // Load the full tour definition (meta + scenes + hotspots) from the API.
  const response = await fetch("/api/tour");
  tour = await response.json();
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(value, max));
}

function positionPromptCard(wrap, prompt) {
  const viewportPadding = 8;
  const gap = 34;

  const wrapRect = wrap.getBoundingClientRect();
  const promptRect = prompt.getBoundingClientRect();
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;

  let left = gap;
  let top = -14;

  if (wrapRect.right + gap + promptRect.width > viewportWidth - viewportPadding) {
    left = -(promptRect.width + gap);
  }

  const minLeft = viewportPadding - wrapRect.left;
  const maxLeft = viewportWidth - viewportPadding - wrapRect.left - promptRect.width;
  left = clamp(left, minLeft, maxLeft);

  const minTop = viewportPadding - wrapRect.top;
  const maxTop = viewportHeight - viewportPadding - wrapRect.top - promptRect.height;
  top = clamp(top, minTop, maxTop);

  prompt.style.left = `${left}px`;
  prompt.style.top = `${top}px`;
}

function createHotspotDom(hotSpotDiv, args) {
  // Pannellum may attach internal nodes to this host; do not wipe innerHTML.
  if (hotSpotDiv.querySelector(".hotspot-wrap")) {
    return;
  }

  const kind = args.kind || "scene";

  // Build custom hotspot UI: pulsing dot plus optional animated hover card.
  const wrap = document.createElement("div");
  wrap.className = `hotspot-wrap hotspot-wrap--${kind}`;

  const dot = document.createElement("div");
  dot.className = "hotspot-dot";
  wrap.appendChild(dot);

  if (
    (args.text && args.text.trim()) ||
    (args.prompt && args.prompt.trim()) ||
    kind === "graph" ||
    kind === "image" ||
    kind === "text"
  ) {
    const prompt = document.createElement("div");
    prompt.className = `prompt-card prompt-card--${kind}`;
    const promptText = document.createElement("div");
    promptText.textContent =
      (kind === "text" ? args.prompt || args.text : args.text || args.prompt) ||
      (kind === "graph" ? "Graphed data" : kind === "image" ? "Image preview" : "Free text");
    prompt.appendChild(promptText);

    // Graph hotspots lazy-load graph image on first hover.
    if (kind === "graph" && args.graph) {
      prompt.classList.add("prompt-card--graph");
      const sizeToCardWidth = {
        s: 640,
        m: 860,
        l: 1100,
      };
      const graphSize = String(args.graph.size || "m").toLowerCase();
      const cardWidth = sizeToCardWidth[graphSize] || sizeToCardWidth.m;
      prompt.style.setProperty("--graph-card-width", `${cardWidth}px`);

      const graphContainer = document.createElement("div");
      graphContainer.className = "graph-container";
      graphContainer.textContent = "Loading graph...";
      prompt.appendChild(graphContainer);

      let lastQueryKey = "";
      wrap.addEventListener("mouseenter", async () => {
        positionPromptCard(wrap, prompt);

        const yColumns = Array.isArray(args.graph.yColumns)
          ? args.graph.yColumns.filter((value) => Boolean(String(value || "").trim()))
          : [args.graph.y].filter((value) => Boolean(String(value || "").trim()));
        const subplotTypes = Array.isArray(args.graph.subplotTypes)
          ? args.graph.subplotTypes.map((value) => String(value || "line").trim().toLowerCase())
          : [];
        const invertedBars = Array.isArray(args.graph.invertedBars)
          ? args.graph.invertedBars.map((value) => value === true || value === "true" || value === "1")
          : [];

        const query = new URLSearchParams({
          csv: args.graph.csv || "",
          animate: String(args.graph.animate === true || args.graph.animate === "true"),
        });
        const effectiveSpeed = getGlobalAnimationSpeed();
        query.set("animationSpeed", String(effectiveSpeed));
        const subplots = Number.parseInt(args.graph.subplots, 10);
        const subplotCount = Number.isFinite(subplots) ? clamp(subplots, 1, 3) : clamp(yColumns.length || 1, 1, 3);
        query.set("subplots", String(subplotCount));
        yColumns.slice(0, subplotCount).forEach((columnName) => {
          query.append("y", columnName);
        });
        for (let idx = 0; idx < subplotCount; idx += 1) {
          query.append("plotType", subplotTypes[idx] || "line");
          query.append("invertBar", invertedBars[idx] ? "true" : "false");
        }
        if (args.graph.x) {
          query.set("x", args.graph.x);
        }
        if (args.graph.yLabel) {
          query.set("yLabel", args.graph.yLabel);
        }
        if (args.graph.yUnit) {
          query.set("yUnit", args.graph.yUnit);
        }
        if (args.graph.renderer) {
          query.set("renderer", args.graph.renderer);
        }

        const queryKey = query.toString();
        if (queryKey === lastQueryKey && graphContainer.querySelector("img")) {
          return;
        }
        lastQueryKey = queryKey;
        graphContainer.textContent = "Loading graph...";

        try {
          const response = await fetch(`/api/graph?${query.toString()}`);
          const body = await response.json();
          if (!response.ok) {
            graphContainer.textContent = body.error || "Failed to generate graph.";
            return;
          }

          const img = document.createElement("img");
          img.className = "graph-preview";
          img.alt = "Generated timeseries graph";
          img.src = `${body.path}?t=${Date.now()}`;
          img.addEventListener("load", () => {
            positionPromptCard(wrap, prompt);
          });

          graphContainer.innerHTML = "";
          graphContainer.appendChild(img);
        } catch (_error) {
          graphContainer.textContent = "Graph request failed.";
        }
      });
    } else if (kind === "image" && args.image) {
      prompt.classList.add("prompt-card--image");
      const imageContainer = document.createElement("div");
      imageContainer.className = "image-container";

      const imagePath = args.image.path || (args.image.file ? `/images2d/${currentAssetTour}/${args.image.file}` : "");
      if (imagePath) {
        const img = document.createElement("img");
        img.className = "image-preview";
        img.alt = "Hotspot image preview";
        img.src = `${imagePath}?t=${Date.now()}`;
        img.addEventListener("load", () => {
          positionPromptCard(wrap, prompt);
        });
        imageContainer.appendChild(img);
      } else {
        imageContainer.textContent = "No image configured.";
      }

      const captionText = String(args.image.caption || "").trim();
      if (captionText) {
        const captionNode = document.createElement("div");
        captionNode.className = "image-caption";
        captionNode.textContent = captionText;
        imageContainer.appendChild(captionNode);
      }
      prompt.appendChild(imageContainer);

      wrap.addEventListener("mouseenter", () => {
        positionPromptCard(wrap, prompt);
      });
    } else {
      wrap.addEventListener("mouseenter", () => {
        positionPromptCard(wrap, prompt);
      });
    }

    wrap.appendChild(prompt);
  }

  hotSpotDiv.classList.add("hotspot-host");
  hotSpotDiv.appendChild(wrap);
}

function toPannellumHotspot(spot) {
  const common = {
    pitch: Number(spot.pitch || 0),
    yaw: Number(spot.yaw || 0),
    createTooltipFunc: createHotspotDom,
    createTooltipArgs: {
      prompt: spot.prompt || "",
      text: spot.text || "",
      kind: spot.kind || "scene",
      graph: spot.graph || null,
      image: spot.image || null,
    },
  };

  if (spot.kind === "graph" || spot.kind === "image" || spot.kind === "text") {
    return {
      ...common,
      type: "info",
      text:
        spot.text ||
        (spot.kind === "graph" ? "Graphed data" : spot.kind === "image" ? "Image" : "Free text"),
    };
  }

  return {
    ...common,
    type: "scene",
    text: spot.text || spot.targetScene || "Open",
    sceneId: spot.targetScene,
  };
}

function toPannellumSceneConfig(scene) {
  // Normalize hotspots so the viewer always receives a list.
  const sourceHotspots = Array.isArray(scene.hotSpots) ? scene.hotSpots : [];

  // Convert our persisted scene shape into Pannellum's expected scene config.
  return {
    title: scene.title || scene.id,
    type: "equirectangular",
    panorama: scene.panorama,
    hotSpots: sourceHotspots.map((spot) => toPannellumHotspot(spot)),
  };
}

function buildViewerConfig(firstSceneOverride = null) {
  if (!tour?.scenes || Object.keys(tour.scenes).length === 0) {
    return null;
  }

  // Build a dictionary of sceneId -> pannellum scene config.
  const scenesConfig = {};
  Object.values(tour.scenes).forEach((scene) => {
    scenesConfig[scene.id] = toPannellumSceneConfig(scene);
  });

  const fallbackFirstScene = tour.meta?.startScene || Object.keys(tour.scenes)[0];
  const firstScene =
    firstSceneOverride && tour.scenes[firstSceneOverride]
      ? firstSceneOverride
      : fallbackFirstScene;

  // "default" config applies viewer-wide behavior.
  return {
    default: {
      firstScene,
      autoLoad: true,
      showControls: true,
      compass: false,
    },
    scenes: scenesConfig,
  };
}

function renderViewer(firstSceneOverride = null) {
  // Recreate viewer whenever scenes/hotspots change.
  if (viewer) {
    viewer.destroy();
    viewer = null;
  }

  const config = buildViewerConfig(firstSceneOverride);
  if (!config) {
    const node = document.getElementById("viewer");
    node.innerHTML =
      "<div class=\"viewer-empty\">Empty tour. Add a scene to begin, or click 'Load Tour From Disk'.</div>";
    return;
  }

  document.getElementById("viewer").innerHTML = "";
  viewer = pannellum.viewer("viewer", config);
}

function fillSceneSelects() {
  // Populate all scene dropdowns from the same scene id list.
  const ids = Object.keys(tour.scenes);
  const optionsHtml = ids.map((id) => `<option value="${id}">${id}</option>`).join("");

  el.sceneSelect.innerHTML = optionsHtml;
  el.hotspotSource.innerHTML = optionsHtml;
  el.hotspotTarget.innerHTML = optionsHtml;

  // Preselect the configured start scene for convenience.
  if (tour.meta?.startScene && ids.includes(tour.meta.startScene)) {
    el.sceneSelect.value = tour.meta.startScene;
    el.hotspotSource.value = tour.meta.startScene;
  } else if (ids.length > 0) {
    el.sceneSelect.value = ids[0];
    el.hotspotSource.value = ids[0];
  }
}

function setStatus(msg, isError = false) {
  // Show success/error feedback in the sidebar.
  el.status.textContent = msg;
  el.status.style.color = isError ? "#ffd0d0" : "#d8ffe0";
}

function updateCurrentTourName(name) {
  const normalized = String(name || "").trim();
  activeTourName = normalized;
  el.currentTourName.textContent = normalized || "(none)";
}

function updateHotspotModeUI() {
  const isGraph = el.hotspotKind.value === "graph";
  const isImage = el.hotspotKind.value === "image";
  const isText = el.hotspotKind.value === "text";
  el.targetSceneWrap.style.display = isGraph || isImage || isText ? "none" : "block";
  el.textContentWrap.style.display = isText ? "block" : "none";
  el.graphCsvWrap.style.display = isGraph ? "block" : "none";
  el.graphXWrap.style.display = isGraph ? "block" : "none";
  el.graphSubplotsWrap.style.display = isGraph ? "block" : "none";
  el.graphYWrap.style.display = isGraph ? "block" : "none";
  el.graphAnimateWrap.style.display = isGraph ? "block" : "none";
  el.imageFileWrap.style.display = isImage ? "block" : "none";
  el.imageCaptionWrap.style.display = isImage ? "block" : "none";
  const wantsCsvUpload = isGraph && !el.hotspotCsv.value;
  el.graphUploadWrap.style.display = wantsCsvUpload ? "block" : "none";
  el.csvUploadButton.style.display = wantsCsvUpload ? "block" : "none";
  el.csvUploadResult.style.display = wantsCsvUpload ? "block" : "none";

  const wantsImageUpload = isImage && !el.hotspotImageFile.value;
  el.imageUploadWrap.style.display = wantsImageUpload ? "block" : "none";
  el.uploadHotspotImageButton.style.display = wantsImageUpload ? "block" : "none";
  el.hotspotImageResult.style.display = wantsImageUpload ? "block" : "none";
}

function updateSceneUploadUI() {
  const wantsImageUpload = !el.newScenePanoramaSelect.value;
  el.sceneUploadWrap.style.display = wantsImageUpload ? "block" : "none";
  el.uploadSceneImageButton.style.display = wantsImageUpload ? "block" : "none";
  el.sceneImageResult.style.display = wantsImageUpload ? "block" : "none";
}

function setPublishStatus(message, isError = false) {
  if (!el.publishResult) {
    return;
  }
  el.publishResult.textContent = message;
  el.publishResult.style.color = isError ? "#ffd0d0" : "#d8ffe0";
}

function updateHelpToggleLabel() {
  const isOpen = Boolean(helpWindowRef && !helpWindowRef.closed);
  if (el.helpToggleButton) {
    el.helpToggleButton.textContent = isOpen ? "Close Tour Help" : "Open Tour Help";
  }
}

function openHelpWindow() {
  helpWindowRef = window.open(
    "/help/new-tour",
    "panocota-new-tour-help",
    "popup=yes,width=920,height=760,resizable=yes,scrollbars=yes",
  );
  if (!helpWindowRef) {
    setStatus("Help popup was blocked by the browser.", true);
    updateHelpToggleLabel();
    return;
  }
  helpWindowRef.focus();
  helpWindowRef.addEventListener("beforeunload", () => {
    helpWindowRef = null;
    updateHelpToggleLabel();
  });
  updateHelpToggleLabel();
}

function closeHelpWindow() {
  if (!helpWindowRef || helpWindowRef.closed) {
    helpWindowRef = null;
    updateHelpToggleLabel();
    return;
  }
  helpWindowRef.close();
  helpWindowRef = null;
  updateHelpToggleLabel();
}

function toggleHelpWindow() {
  const isOpen = Boolean(helpWindowRef && !helpWindowRef.closed);
  if (isOpen) {
    closeHelpWindow();
    setStatus("Tour help window closed.");
  } else {
    openHelpWindow();
    if (helpWindowRef && !helpWindowRef.closed) {
      setStatus("Tour help window opened.");
    }
  }
}

function setupEvents() {
  el.helpToggleButton.addEventListener("click", toggleHelpWindow);

  el.refreshTours.addEventListener("click", async () => {
    try {
      await refreshTourList(resolveLoadTourName(), activeTourName);
      setStatus("Tour list refreshed.");
    } catch (_error) {
      setStatus("Failed to refresh tour list.", true);
    }
  });

  el.saveTourSelect.addEventListener("change", updateSaveTourUI);

  el.hotspotKind.addEventListener("change", updateHotspotModeUI);
  el.globalAnimationSpeed.addEventListener("change", () => {
    if (viewer) {
      const activeScene = viewer.getScene();
      renderViewer(activeScene || null);
    }
    setStatus("Global graph animation speed updated.");
  });
  el.hotspotSubplots.addEventListener("change", () => {
    const existing = getSelectedSubplotConfigs();
    renderSubplotConfigRows(existing);
  });
  el.hotspotImageFile.addEventListener("change", () => {
    if (el.hotspotImageFile.value) {
      el.hotspotImageResult.textContent = "";
    }
    updateHotspotModeUI();
  });
  el.hotspotCsv.addEventListener("change", async () => {
    el.csvUploadResult.textContent = "";
    updateHotspotModeUI();
    const existing = getSelectedSubplotConfigs();
    try {
      await refreshColumnSelects("", existing);
      setStatus("Loaded CSV columns.");
    } catch (_error) {
      setStatus("Failed to load CSV columns for selected file.", true);
    }
  });

  // Jump to the scene currently selected in the dropdown.
  el.jumpScene.addEventListener("click", () => {
    if (!viewer) {
      setStatus("No scene is loaded yet. Add or load a tour first.", true);
      return;
    }
    const selected = el.sceneSelect.value;
    if (!selected) {
      setStatus("Select a scene first.", true);
      return;
    }
    viewer.loadScene(selected);
    el.hotspotSource.value = selected;
  });

  // Delete the selected scene and remove nav hotspots that target it.
  el.deleteScene.addEventListener("click", () => {
    const selected = el.sceneSelect.value;
    if (!selected || !tour.scenes[selected]) {
      setStatus("Select an existing scene to delete.", true);
      return;
    }

    const ok = window.confirm(`Delete scene '${selected}'? This cannot be undone.`);
    if (!ok) {
      return;
    }

    delete tour.scenes[selected];

    // Remove navigation hotspots that pointed to the deleted scene.
    Object.values(tour.scenes).forEach((scene) => {
      if (!Array.isArray(scene.hotSpots)) {
        return;
      }
      scene.hotSpots = scene.hotSpots.filter((spot) => {
        if ((spot.kind || "scene") !== "scene") {
          return true;
        }
        return spot.targetScene !== selected;
      });
    });

    const remaining = Object.keys(tour.scenes);
    if (!remaining.includes(tour.meta?.startScene)) {
      tour.meta.startScene = remaining[0] || null;
    }

    fillSceneSelects();
    renderViewer();
    setStatus(`Deleted scene '${selected}'.`);
  });

  // Create a new scene in memory, then rerender viewer + controls.
  el.addScene.addEventListener("click", () => {
    const title = el.newSceneTitle.value.trim();
    const id = title;
    const imageName = el.newScenePanoramaSelect.value.trim();
    const panorama = imageName ? `/images360/${currentAssetTour}/${imageName}` : "";

    if (!title || !panorama) {
      setStatus("Scene title and panorama image are required.", true);
      return;
    }

    if (tour.scenes[id]) {
      setStatus("A scene with this title already exists.", true);
      return;
    }

    // Scene objects use the same shape as tour_data/tour.json.
    tour.scenes[id] = {
      id,
      title,
      panorama,
      hotSpots: [],
    };

    if (!tour.meta.startScene) {
      // First scene added becomes start scene by default.
      tour.meta.startScene = id;
    }

    fillSceneSelects();
    renderViewer();
    el.sceneImageResult.textContent = "";
    setStatus(`Added scene '${id}'.`);
  });

  el.newScenePanoramaSelect.addEventListener("change", () => {
    if (el.newScenePanoramaSelect.value) {
      el.sceneImageResult.textContent = "";
    }
    updateSceneUploadUI();
  });

  el.uploadSceneImageButton.addEventListener("click", async () => {
    const file = el.sceneImageUpload.files?.[0];
    if (!file) {
      el.sceneImageResult.textContent = "Select an image first.";
      return;
    }

    const data = new FormData();
    data.append("image", file);

    const response = await fetch("/api/upload_360", {
      method: "POST",
      body: data,
    });

    const body = await response.json();
    if (!response.ok) {
      el.sceneImageResult.textContent = body.error || "Upload failed.";
      return;
    }

    el.sceneImageResult.textContent = `Uploaded: ${body.filename}`;
    try {
      await refreshImageList(body.filename);
      updateSceneUploadUI();
    } catch (_error) {
      setStatus("Image uploaded, but failed to refresh image list.", true);
    }
    setStatus("Image upload complete. Selected for new scene.");
  });

  el.uploadHotspotImageButton.addEventListener("click", async () => {
    const file = el.hotspotImageUpload.files?.[0];
    if (!file) {
      el.hotspotImageResult.textContent = "Select an image first.";
      return;
    }

    const data = new FormData();
    data.append("image", file);

    const response = await fetch("/api/upload_2d", {
      method: "POST",
      body: data,
    });

    const body = await response.json();
    if (!response.ok) {
      el.hotspotImageResult.textContent = body.error || "Upload failed.";
      return;
    }

    el.hotspotImageResult.textContent = `Uploaded: ${body.filename}`;
    try {
      await refreshImageList("", body.filename);
      updateHotspotModeUI();
    } catch (_error) {
      setStatus("Image uploaded, but failed to refresh image list.", true);
    }
    setStatus("Image upload complete. Selected for image hotspot.");
  });

  // Capture current camera view for precise hotspot placement.
  el.captureView.addEventListener("click", () => {
    if (!viewer) {
      setStatus("Viewer is empty. Add or load at least one scene first.", true);
      return;
    }
    const pitch = viewer.getPitch();
    const yaw = viewer.getYaw();
    el.hotspotPitch.value = pitch.toFixed(2);
    el.hotspotYaw.value = yaw.toFixed(2);
    setStatus("Captured current view pitch/yaw.");
  });

  // Append a hotspot to source scene that navigates to target scene.
  el.addHotspot.addEventListener("click", () => {
    const kind = el.hotspotKind.value;
    const source = el.hotspotSource.value;
    const target = el.hotspotTarget.value;
    const pitch = Number(el.hotspotPitch.value);
    const yaw = Number(el.hotspotYaw.value);
    const text =
      el.hotspotLabel.value.trim() ||
      (kind === "graph"
        ? "View graphed data"
        : kind === "image"
          ? "View image"
          : kind === "text"
            ? "View text"
            : `Go to ${target}`);

    if (!tour.scenes[source]) {
      setStatus("Source scene must exist.", true);
      return;
    }

    if (Number.isNaN(pitch) || Number.isNaN(yaw)) {
      setStatus("Pitch and yaw must be numeric.", true);
      return;
    }

    if (kind === "graph") {
      const csv = el.hotspotCsv.value.trim();
      const x = el.hotspotX.value.trim();
      const subplots = Number.parseInt(el.hotspotSubplots.value, 10);
      const subplotCount = Number.isFinite(subplots) ? clamp(subplots, 1, 3) : 1;
      const subplotConfigs = getSelectedSubplotConfigs().slice(0, subplotCount);
      const yColumns = subplotConfigs.map((item) => item.y).filter((value) => Boolean(value));
      const subplotTypes = subplotConfigs.map((item) => {
        const normalized = String(item.type || "line").toLowerCase();
        return ["line", "scatter", "bar"].includes(normalized) ? normalized : "line";
      });
      const invertedBars = subplotConfigs.map((item) => Boolean(item.invertBar));
      const animate = el.hotspotAnimate.value === "true";
      const animationSpeed = getGlobalAnimationSpeed();

      if (!csv || yColumns.length !== subplotCount || subplotTypes.length !== subplotCount) {
        setStatus("Graph hotspots require CSV plus one Y column per subplot.", true);
        return;
      }

      tour.scenes[source].hotSpots.push({
        kind: "graph",
        pitch,
        yaw,
        text,
        prompt: text,
        graph: {
          csv,
          x,
          y: yColumns[0],
          yColumns,
          subplots: subplotCount,
          subplotTypes,
          invertedBars,
          animate,
          animationSpeed,
          size: "m",
        },
      });
      el.csvUploadResult.textContent = "";
      setStatus(`Added graph hotspot in '${source}'.`);
    } else if (kind === "image") {
      const fileName = el.hotspotImageFile.value.trim();
      const caption = el.hotspotImageCaption.value.trim();
      if (!fileName) {
        setStatus("Image hotspots require an image file.", true);
        return;
      }

      tour.scenes[source].hotSpots.push({
        kind: "image",
        pitch,
        yaw,
        text,
        prompt: text,
        image: {
          file: fileName,
          path: `/images2d/${currentAssetTour}/${fileName}`,
          caption,
        },
      });
      el.hotspotImageResult.textContent = "";
      setStatus(`Added image hotspot in '${source}'.`);
    } else if (kind === "text") {
      const freeText = el.hotspotFreeText.value.trim();
      if (!freeText) {
        setStatus("Free text hotspots require text content.", true);
        return;
      }

      tour.scenes[source].hotSpots.push({
        kind: "text",
        pitch,
        yaw,
        text,
        prompt: freeText,
      });
      setStatus(`Added free text hotspot in '${source}'.`);
    } else {
      if (!tour.scenes[target]) {
        setStatus("Target scene must exist for navigation hotspots.", true);
        return;
      }

      tour.scenes[source].hotSpots.push({
        kind: "scene",
        pitch,
        yaw,
        targetScene: target,
        text,
        prompt: text,
      });
      setStatus(`Added hotspot in '${source}' to '${target}'.`);
    }

    // Prefer incremental hotspot insert to avoid tearing down WebGL context.
    const newSpot = tour.scenes[source].hotSpots[tour.scenes[source].hotSpots.length - 1];
    const panoSpot = toPannellumHotspot(newSpot);
    if (!viewer) {
      renderViewer(source);
      return;
    }
    try {
      viewer.addHotSpot(panoSpot, source);
      if (viewer.getScene() !== source) {
        setStatus(
          `Hotspot added to '${source}'. Open that scene to see it.`,
          false,
        );
      }
    } catch (_error) {
      // Fall back to full rerender if incremental add is not possible.
      renderViewer(source);
    }
  });

  // Persist current in-memory tour to backend JSON file.
  el.saveTour.addEventListener("click", async () => {
    const tourName = resolveSaveTourName();
    if (!tourName) {
      setStatus("Provide a tour name to create a new tour.", true);
      return;
    }
    if (!tour.meta.startScene) {
      // Ensure saved data always has a valid start scene when possible.
      tour.meta.startScene = Object.keys(tour.scenes)[0] || null;
    }

    const response = await fetch("/api/tour/save", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        name: tourName,
        tour,
      }),
    });

    const body = await response.json();
    if (response.ok) {
      const savedName = body.name || tourName;
      updateCurrentTourName(savedName);
      try {
        await refreshTourList(savedName, savedName);
        await refreshImageList("");
        await refreshCsvSelects();
      } catch (_error) {
        // Keep save successful even when list refresh fails.
      }
      setStatus(`Tour '${savedName}' saved to disk.`);
    } else {
      setStatus(body.error || "Failed to save tour.", true);
    }
  });

  el.loadTourButton.addEventListener("click", async () => {
    const tourName = resolveLoadTourName();
    if (!tourName) {
      setStatus("Select a saved tour to load.", true);
      return;
    }
    const response = await fetch("/api/tour/load", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name: tourName }),
    });

    const body = await response.json();
    if (!response.ok) {
      setStatus(body.error || "Failed to load saved tour.", true);
      return;
    }

    tour = body.tour || body;
    const loadedName = body.name || tourName;
    updateCurrentTourName(loadedName);
    if (!tour.meta) {
      tour.meta = {};
    }
    if (!tour.scenes) {
      tour.scenes = {};
    }

    fillSceneSelects();
    renderViewer();
    try {
      await refreshTourList(loadedName, loadedName);
      await refreshImageList("");
      await refreshCsvSelects();
    } catch (_error) {
      // Load is complete; tour list refresh failure is non-fatal.
    }
    setStatus(`Tour '${loadedName}' loaded from disk.`);
  });

  el.closeTourButton.addEventListener("click", async () => {
    const response = await fetch("/api/tour/close", {
      method: "POST",
    });

    const body = await response.json();
    if (!response.ok) {
      setStatus(body.error || "Failed to close tour.", true);
      return;
    }

    tour = body.tour || { meta: {}, scenes: {} };
    if (!tour.meta) {
      tour.meta = {};
    }
    if (!tour.scenes) {
      tour.scenes = {};
    }

    fillSceneSelects();
    renderViewer();
    try {
      await refreshTourList("", "");
      await refreshImageList("");
      await refreshCsvSelects();
    } catch (_error) {
      // Close completed; asset list refresh failure is non-fatal.
    }
    updateCurrentTourName("");
    setStatus(`Closed tour '${body.closed || "tour"}' and cleared ${body.removedGraphs || 0} cached graphs.`);
  });

  el.deleteTourButton.addEventListener("click", async () => {
    const tourName = resolveLoadTourName();
    if (!tourName) {
      setStatus("Select a saved tour to delete.", true);
      return;
    }
    const ok = window.confirm(`Delete saved tour '${tourName}' from disk?`);
    if (!ok) {
      return;
    }

    const response = await fetch("/api/tour/delete", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name: tourName }),
    });

    const body = await response.json();
    if (!response.ok) {
      setStatus(body.error || "Failed to delete tour.", true);
      return;
    }

    try {
      await refreshTourList("", "");
    } catch (_error) {
      // Deletion succeeded; list refresh failure is non-fatal.
    }
    setStatus(`Tour '${body.name || tourName}' deleted from disk.`);
  });

  el.csvUploadButton.addEventListener("click", async () => {
    const file = el.csvUploadInput.files?.[0];
    if (!file) {
      el.csvUploadResult.textContent = "Select a CSV file first.";
      return;
    }

    const data = new FormData();
    data.append("datafile", file);

    const response = await fetch("/api/upload_csv", {
      method: "POST",
      body: data,
    });

    const body = await response.json();
    if (!response.ok) {
      el.csvUploadResult.textContent = body.error || "CSV upload failed.";
      return;
    }

    el.csvUploadResult.textContent = `Uploaded: ${body.filename}`;
    try {
      await refreshCsvSelects(body.filename);
      updateHotspotModeUI();
    } catch (_error) {
      setStatus("CSV uploaded, but failed to refresh CSV dropdowns.", true);
    }
    setStatus("CSV upload complete. Filename prefilled for graph hotspots.");
  });

  el.publishTourButton.addEventListener("click", async () => {
    const owner = (el.publishOwner.value || "").trim();
    const repo = (el.publishRepo.value || "").trim();
    const scope = (el.publishScope.value || "current").trim().toLowerCase();
    const branch = (el.publishBranch.value || "main").trim() || "main";
    const githubToken = (el.publishToken.value || "").trim();
    const isOrg = (el.publishOwnerType.value || "user") === "org";
    const privateRepo = Boolean(el.publishPrivate.checked);

    if (!owner) {
      setPublishStatus("GitHub owner is required.", true);
      return;
    }

    let selectedTour = "";
    if (scope !== "all") {
      selectedTour = (activeTourName || "").trim();
      if (!selectedTour) {
        setPublishStatus("Load or save a current tour first, or switch scope to All Saved Tours.", true);
        return;
      }
    }

    setPublishStatus("Publishing static package to GitHub...");

    try {
      const response = await fetch("/api/publish/github", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          all: scope === "all",
          tour: selectedTour,
          owner,
          repo,
          githubToken,
          githubOrg: isOrg,
          privateRepo,
          branch,
        }),
      });

      const body = await response.json();
      if (!response.ok) {
        setPublishStatus(body.error || "Publish failed.", true);
        return;
      }

      const tours = Array.isArray(body.exported) ? body.exported.join(", ") : "";
      setPublishStatus(`Published ${tours} to ${body.repoUrl || `${owner}/${body.repo}`}.`);
      setStatus("GitHub publish completed.");
    } catch (_error) {
      setPublishStatus("Publish request failed.", true);
    } finally {
      // Do not keep tokens in the form after a request completes.
      el.publishToken.value = "";
    }
  });
}

async function boot() {
  try {
    // Always start panel scroll at top on refresh/reload.
    if (window.history && "scrollRestoration" in window.history) {
      window.history.scrollRestoration = "manual";
    }
    const panelNode = document.querySelector(".panel");
    if (panelNode) {
      panelNode.scrollTop = 0;
    }
    window.scrollTo(0, 0);
    updateCurrentTourName("");

    // Always reset app session to no active tour on open.
    try {
      const closeResponse = await fetch("/api/tour/close", { method: "POST" });
      const closeBody = await closeResponse.json();
      if (closeResponse.ok && closeBody?.tour) {
        tour = closeBody.tour;
        updateCurrentTourName("");
      } else {
        await loadTour();
      }
    } catch (_error) {
      await loadTour();
    }

    // 1) Ensure expected top-level keys, 2) render + bind events.
    if (!tour.meta) {
      tour.meta = {};
    }
    if (!tour.scenes) {
      tour.scenes = {};
    }

    fillSceneSelects();
    renderViewer();
    await refreshTourList("", "");
    await refreshImageList("");
    await refreshCsvSelects();
    setupEvents();
    updateSceneUploadUI();
    updateHotspotModeUI();
    setStatus("Opened with no active tour. Add scenes or load from disk.");
  } catch (error) {
    // Any fetch/parse/init issue lands here.
    setStatus("Failed to load tour data.", true);
    console.error(error);
  }
}

// Start app initialization when script loads.
boot();
