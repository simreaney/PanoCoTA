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
let pendingHotspotPlacement = null;
let hotspotPanelMode = "none";
let hotspotMoveMode = false;
let hotspotDeleteMode = false;
let dragState = null;
const HOTSPOT_DRAG_THRESHOLD_PX = 6;
let hotspotIdCounter = 0;
let viewerCursorIndicator = null;
let placementPointerState = null;
const graphRequestCache = new Map();
let publishStatusPollTimer = null;
const SUBPLOT_COLOR_OPTIONS = [
  { value: "red", label: "Red" },
  { value: "blue", label: "Blue" },
  { value: "green", label: "Green" },
  { value: "orange", label: "Orange" },
  { value: "purple", label: "Purple" },
  { value: "teal", label: "Teal" },
  { value: "brown", label: "Brown" },
  { value: "black", label: "Black" },
  { value: "gray", label: "Gray" },
  { value: "pink", label: "Pink" },
];

const DEFAULT_GRAPH_SECONDS_PER_FRAME = 0.1;

function runWhenIdle(task) {
  if (typeof window.requestIdleCallback === "function") {
    window.requestIdleCallback(() => task(), { timeout: 1200 });
    return;
  }
  window.setTimeout(task, 120);
}

function asTruthy(value) {
  if (value === true || value === 1) {
    return true;
  }
  const text = String(value || "").trim().toLowerCase();
  return text === "true" || text === "1" || text === "yes" || text === "on";
}

async function requestGraphAsset(queryKey) {
  if (graphRequestCache.has(queryKey)) {
    return graphRequestCache.get(queryKey);
  }

  const requestPromise = (async () => {
    const response = await fetch(`/api/graph?${queryKey}`);
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.error || "Failed to generate graph.");
    }
    return body;
  })();

  graphRequestCache.set(queryKey, requestPromise);
  try {
    const result = await requestPromise;
    graphRequestCache.set(queryKey, Promise.resolve(result));
    return result;
  } catch (error) {
    graphRequestCache.delete(queryKey);
    throw error;
  }
}

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
  hotspotTarget: document.getElementById("hotspot-target"),
  hotspotLabel: document.getElementById("hotspot-label"),
  textContentWrap: document.getElementById("text-content-wrap"),
  hotspotFreeText: document.getElementById("hotspot-free-text"),
  hotspotCsv: document.getElementById("hotspot-csv"),
  hotspotX: document.getElementById("hotspot-x"),
  hotspotSubplots: document.getElementById("hotspot-subplots"),
  hotspotYSelects: document.getElementById("hotspot-y-selects"),
  hotspotAnimate: document.getElementById("hotspot-animate"),
  hotspotImageFile: document.getElementById("hotspot-image-file"),
  imageCaptionWrap: document.getElementById("image-caption-wrap"),
  hotspotImageCaption: document.getElementById("hotspot-image-caption"),
  hotspotImageUpload: document.getElementById("hotspot-image-upload"),
  uploadHotspotImageButton: document.getElementById("upload-hotspot-image"),
  hotspotImageResult: document.getElementById("hotspot-image-result"),
  placeHotspotButton: document.getElementById("place-hotspot"),
  hotspotModeAddButton: document.getElementById("hotspot-mode-add"),
  hotspotModeMoveButton: document.getElementById("hotspot-mode-move"),
  hotspotModeDeleteButton: document.getElementById("hotspot-mode-delete"),
  hotspotAddForm: document.getElementById("hotspot-add-form"),
  targetSceneWrap: document.getElementById("target-scene-wrap"),
  graphCsvWrap: document.getElementById("graph-csv-wrap"),
  graphXWrap: document.getElementById("graph-x-wrap"),
  graphSubplotsWrap: document.getElementById("graph-subplots-wrap"),
  graphYWrap: document.getElementById("graph-y-wrap"),
  graphAnimateWrap: document.getElementById("graph-animate-wrap"),
  graphUploadWrap: document.getElementById("graph-upload-wrap"),
  imageFileWrap: document.getElementById("image-file-wrap"),
  imageUploadWrap: document.getElementById("image-upload-wrap"),
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

function resolveWriteTourName() {
  const saveName = resolveSaveTourName();
  if (saveName) {
    return saveName;
  }
  if (activeTourName) {
    return activeTourName;
  }
  return currentAssetTour || "tour";
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

async function refreshImageList(preferredImage = "", preferredHotspotImage = "", tourName = "") {
  const targetTour = (tourName || resolveWriteTourName()).trim();
  const query = targetTour ? `?tour=${encodeURIComponent(targetTour)}` : "";
  const [panoramaResponse, image2dResponse] = await Promise.all([
    fetch(`/api/images_360${query}`),
    fetch(`/api/images_2d${query}`),
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

async function fetchCsvFiles(tourName = "") {
  const targetTour = (tourName || resolveWriteTourName()).trim();
  const query = targetTour ? `?tour=${encodeURIComponent(targetTour)}` : "";
  const response = await fetch(`/api/csvs${query}`);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Failed to fetch CSV list.");
  }
  currentAssetTour = body.tour || currentAssetTour;
  return Array.isArray(body.files) ? body.files : [];
}

async function fetchCsvColumns(csvName, tourName = "") {
  if (!csvName) {
    return [];
  }

  const query = new URLSearchParams({ csv: csvName });
  const targetTour = (tourName || resolveWriteTourName()).trim();
  if (targetTour) {
    query.set("tour", targetTour);
  }
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
    const colorNode = row.querySelector(".subplot-color-select");
    return {
      y: (yNode?.value || "").trim(),
      type: (typeNode?.value || "line").trim().toLowerCase(),
      invertBar: Boolean(invertNode?.checked),
      color: (colorNode?.value || "").trim().toLowerCase(),
    };
  });
}

function updateInvertToggleVisibility() {
  return;
}

function renderSubplotConfigRows(preferredConfigs = []) {
  const requested = Number.parseInt(el.hotspotSubplots.value, 10);
  const subplotCount = Number.isFinite(requested) ? clamp(requested, 1, 3) : 1;
  const html = [];
  const defaultColors = SUBPLOT_COLOR_OPTIONS.map((item) => item.value);

  for (let index = 0; index < subplotCount; index += 1) {
    const preferred = preferredConfigs[index] || {};
    const preferredType = ["line", "scatter", "bar"].includes(preferred.type)
      ? preferred.type
      : "line";
    const preferredColor = String(preferred.color || defaultColors[index % defaultColors.length]).toLowerCase();
    const colorOptionsHtml = SUBPLOT_COLOR_OPTIONS.map(
      (option) =>
        `<option value="${option.value}" ${preferredColor === option.value ? "selected" : ""}>${option.label}</option>`,
    ).join("");
    html.push(
      `<div class="subplot-config-row">
        <label class="subplot-y-label">Subplot ${index + 1} Y Column<select class="subplot-y-select" id="hotspot-y-${index}"></select></label>
        <label class="subplot-type-label">Type<select class="subplot-type-select" id="hotspot-type-${index}">
          <option value="line" ${preferredType === "line" ? "selected" : ""}>Line</option>
          <option value="scatter" ${preferredType === "scatter" ? "selected" : ""}>Scatter</option>
          <option value="bar" ${preferredType === "bar" ? "selected" : ""}>Bar</option>
        </select></label>
        <label class="subplot-color-label">Color<select class="subplot-color-select" id="hotspot-color-${index}">${colorOptionsHtml}</select></label>
        <label class="subplot-invert-label"><input class="subplot-invert-check" id="hotspot-invert-${index}" type="checkbox" ${preferred.invertBar ? "checked" : ""} /> Invert Y axis</label>
      </div>`,
    );
  }
  el.hotspotYSelects.innerHTML = html.join("");

  const selects = Array.from(el.hotspotYSelects.querySelectorAll(".subplot-y-select"));
  selects.forEach((selectEl, index) => {
    const preferred = preferredConfigs[index]?.y || "";
    setSelectOptions(selectEl, csvColumns, false, "", preferred);
  });

  updateInvertToggleVisibility();
}

async function refreshColumnSelects(preferredX = "", preferredConfigs = [], tourName = "") {
  const selectedCsv = el.hotspotCsv.value;
  csvColumns = await fetchCsvColumns(selectedCsv, tourName);

  setSelectOptions(el.hotspotX, csvColumns, true, "(auto index)", preferredX);
  renderSubplotConfigRows(preferredConfigs);
}

async function refreshCsvSelects(preferredCsv = "", preferredX = "", preferredConfigs = [], tourName = "") {
  const targetTour = (tourName || resolveWriteTourName()).trim();
  csvFiles = await fetchCsvFiles(targetTour);
  setSelectOptions(el.hotspotCsv, csvFiles, true, "(upload new csv)", preferredCsv);

  if (csvFiles.length === 0) {
    setSelectOptions(el.hotspotX, [], true, "(auto index)", "");
    csvColumns = [];
    renderSubplotConfigRows([]);
    return;
  }

  await refreshColumnSelects(preferredX, preferredConfigs, targetTour);
}

async function loadTour() {
  // Load the full tour definition (meta + scenes + hotspots) from the API.
  const response = await fetch("/api/tour");
  tour = await response.json();
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(value, max));
}

function getAdaptiveGraphPreviewMaxPoints() {
  const baselinePoints = 2200;
  const baselineArea = 1920 * 1080;
  const currentArea = Math.max(window.innerWidth, 1) * Math.max(window.innerHeight, 1);
  const areaScale = clamp(currentArea / baselineArea, 0.65, 2.4);
  return Math.round(clamp(baselinePoints * areaScale, 1400, 5200));
}

function positionPromptCard(wrap, prompt) {
  const viewportPadding = 8;
  const gap = 34;
  const isMediaPrompt =
    prompt.classList.contains("prompt-card--graph") ||
    prompt.classList.contains("prompt-card--image");

  const wrapRect = wrap.getBoundingClientRect();
  const promptRect = prompt.getBoundingClientRect();
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  const viewerRect = document.getElementById("viewer")?.getBoundingClientRect();

  let left = gap;
  let top = -14;

  if (isMediaPrompt && viewerRect) {
    // Keep large media cards centered vertically in the panorama for consistent readability.
    top = (viewerRect.top + (viewerRect.height / 2)) - wrapRect.top - (promptRect.height / 2);
  }

  if (wrapRect.right + gap + promptRect.width > viewportWidth - viewportPadding) {
    left = -(promptRect.width + gap);
  }

  const minLeft = viewportPadding - wrapRect.left;
  const maxLeft = viewportWidth - viewportPadding - wrapRect.left - promptRect.width;
  left = clamp(left, minLeft, maxLeft);

  const topMinBoundary = viewerRect ? viewerRect.top + viewportPadding : viewportPadding;
  const topMaxBoundary = viewerRect
    ? viewerRect.bottom - viewportPadding
    : viewportHeight - viewportPadding;
  const minTop = topMinBoundary - wrapRect.top;
  const maxTop = topMaxBoundary - wrapRect.top - promptRect.height;
  top = clamp(top, minTop, maxTop);

  prompt.style.left = `${Math.round(left)}px`;
  prompt.style.top = `${Math.round(top)}px`;
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

  if (args.interactive) {
    wrap.classList.add("hotspot-wrap--editable");
    wrap.title = hotspotDeleteMode ? "Click to delete hotspot" : "Left-drag to move hotspot";
    attachHotspotMoveHandlers(wrap, hotSpotDiv, args.sceneId, args.hotspotIndex);
  }

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
      const parsedSubplots = Number.parseInt(args.graph.subplots, 10);
      const yColumnsHint = Array.isArray(args.graph.yColumns)
        ? args.graph.yColumns.filter((value) => Boolean(String(value || "").trim()))
        : [args.graph.y].filter((value) => Boolean(String(value || "").trim()));
      const subplotCountHint = Number.isFinite(parsedSubplots)
        ? clamp(parsedSubplots, 1, 3)
        : clamp(yColumnsHint.length || 1, 1, 3);
      const cardWidth = 700;
      prompt.style.setProperty("--graph-card-width", `${cardWidth}px`);

      const graphContainer = document.createElement("div");
      graphContainer.className = "graph-container";
      graphContainer.textContent = "Loading graph...";
      prompt.appendChild(graphContainer);

      const buildGraphQuery = () => {
        const yColumns = Array.isArray(args.graph.yColumns)
          ? args.graph.yColumns.filter((value) => Boolean(String(value || "").trim()))
          : [args.graph.y].filter((value) => Boolean(String(value || "").trim()));
        const subplotTypes = Array.isArray(args.graph.subplotTypes)
          ? args.graph.subplotTypes.map((value) => String(value || "line").trim().toLowerCase())
          : [];
        const subplotColors = Array.isArray(args.graph.subplotColors)
          ? args.graph.subplotColors.map((value) => String(value || "").trim().toLowerCase())
          : [];
        const invertedBars = Array.isArray(args.graph.invertedBars)
          ? args.graph.invertedBars.map((value) => asTruthy(value))
          : [];

        const query = new URLSearchParams({
          csv: args.graph.csv || "",
          animate: String(asTruthy(args.graph.animate)),
        });
        const graphTour = resolveWriteTourName();
        if (graphTour) {
          query.set("tour", graphTour);
        }
        query.set("maxPoints", String(getAdaptiveGraphPreviewMaxPoints()));
        query.set("animationSpeed", String(DEFAULT_GRAPH_SECONDS_PER_FRAME));
        const subplots = Number.parseInt(args.graph.subplots, 10);
        const subplotCount = Number.isFinite(subplots) ? clamp(subplots, 1, 3) : clamp(yColumns.length || 1, 1, 3);
        query.set("subplots", String(subplotCount));
        yColumns.slice(0, subplotCount).forEach((columnName) => {
          query.append("y", columnName);
        });
        for (let idx = 0; idx < subplotCount; idx += 1) {
          query.append("plotType", subplotTypes[idx] || "line");
          query.append("color", subplotColors[idx] || SUBPLOT_COLOR_OPTIONS[idx % SUBPLOT_COLOR_OPTIONS.length].value);
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
        const requestedRenderer = String(args.graph.renderer || "").trim().toLowerCase();
        if (subplotCount > 1) {
          query.set("renderer", "matplotlib");
        } else if (requestedRenderer) {
          query.set("renderer", requestedRenderer);
        }
        return query.toString();
      };

      let lastQueryKey = "";
      const resetGraphPreview = () => {
        lastQueryKey = "";
        graphContainer.replaceChildren();
        graphContainer.textContent = "Loading graph...";
      };
      wrap.addEventListener("mouseenter", async () => {
        positionPromptCard(wrap, prompt);

        const queryKey = buildGraphQuery();
        if (queryKey === lastQueryKey && graphContainer.querySelector("img")) {
          return;
        }
        lastQueryKey = queryKey;
        graphContainer.textContent = "Loading graph...";

        try {
          const body = await requestGraphAsset(queryKey);

          const img = document.createElement("img");
          img.className = "graph-preview";
          img.alt = "Generated timeseries graph";
          img.src = `${body.path}?t=${Date.now()}`;
          img.addEventListener("load", () => {
            positionPromptCard(wrap, prompt);
          });

          graphContainer.innerHTML = "";
          graphContainer.appendChild(img);
          if (body.sampled) {
            const note = document.createElement("div");
            note.className = "graph-preview-note";
            const plotted = Number(body.plottedPoints || 0);
            const original = Number(body.originalPoints || 0);
            note.textContent =
              plotted > 0 && original > 0
                ? `Preview uses ${plotted} of ${original} points for editor performance. Exported graphics include the full dataset.`
                : "Preview may be downsampled for editor performance. Exported graphics include the full dataset.";
            graphContainer.appendChild(note);
          }
        } catch (error) {
          graphContainer.textContent = error?.message || "Graph request failed.";
        }
      });

      wrap.addEventListener("mouseleave", () => {
        resetGraphPreview();
      });

      runWhenIdle(() => {
        const queryKey = buildGraphQuery();
        if (!queryKey) {
          return;
        }
        requestGraphAsset(queryKey).catch(() => {
          // Ignore prefetch errors; hover request will show user-facing feedback.
        });
      });
    } else if (kind === "image" && args.image) {
      prompt.classList.add("prompt-card--image");
      prompt.style.setProperty("--image-card-width", "680px");
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

function nextHotspotId() {
  hotspotIdCounter += 1;
  return `hotspot-${hotspotIdCounter}`;
}

function ensureHotspotIds() {
  let highestId = hotspotIdCounter;
  Object.values(tour?.scenes || {}).forEach((scene) => {
    if (!Array.isArray(scene.hotSpots)) {
      scene.hotSpots = [];
      return;
    }
    scene.hotSpots.forEach((spot) => {
      const existingId = String(spot.id || "").trim();
      if (existingId) {
        const match = /^hotspot-(\d+)$/.exec(existingId);
        if (match) {
          highestId = Math.max(highestId, Number.parseInt(match[1], 10));
        }
        return;
      }
      spot.id = nextHotspotId();
    });
  });
  hotspotIdCounter = Math.max(hotspotIdCounter, highestId);
}

function findHotspot(sceneId, hotspotIndex) {
  const scene = tour?.scenes?.[sceneId];
  if (!scene || !Array.isArray(scene.hotSpots)) {
    return null;
  }
  return scene.hotSpots[hotspotIndex] || null;
}

function updateHotspotPositionFields(sceneId) {
  if (el.sceneSelect && sceneId) {
    el.sceneSelect.value = sceneId;
  }
}

function getActiveViewerSceneId() {
  if (viewer && typeof viewer.getScene === "function") {
    const activeScene = viewer.getScene();
    if (activeScene) {
      return activeScene;
    }
  }
  return el.sceneSelect.value || tour?.meta?.startScene || Object.keys(tour?.scenes || {})[0] || "";
}

function syncHotspotSourceSelection() {
  const activeScene = getActiveViewerSceneId();
  if (activeScene && tour?.scenes?.[activeScene] && el.sceneSelect) {
    el.sceneSelect.value = activeScene;
  }
}

function ensureViewerCursorIndicator() {
  return viewerCursorIndicator;
}

function setViewerCursorIndicatorTone(clientX, clientY) {
  void clientX;
  void clientY;
}

function hideViewerCursorIndicator() {
  return;
}

function updateViewerCursorIndicator(event) {
  void event;
}

function syncHotspotInViewer(sceneId, hotspotIndex) {
  if (!viewer || viewer.getScene() !== sceneId) {
    return false;
  }

  const spot = findHotspot(sceneId, hotspotIndex);
  if (!spot?.id) {
    return false;
  }

  try {
    viewer.removeHotSpot(spot.id, sceneId);
  } catch (_error) {
    // Ignore missing hotspot; addHotSpot below is authoritative.
  }

  try {
    viewer.addHotSpot(toPannellumHotspot({ ...spot, sceneId, hotspotIndex }), sceneId);
    return true;
  } catch (_error) {
    return false;
  }
}

function renderViewerPreservingView() {
  if (!viewer) {
    renderViewer();
    return;
  }

  const activeScene = viewer.getScene();
  const pitch = viewer.getPitch();
  const yaw = viewer.getYaw();
  const hfov = viewer.getHfov();
  renderViewer(activeScene || null);
  if (viewer && activeScene) {
    viewer.lookAt(pitch, yaw, hfov, false);
  }
}

function refreshHotspotInteractivityInViewer() {
  const sceneId = getActiveViewerSceneId();
  if (!sceneId || !viewer || viewer.getScene() !== sceneId) {
    renderViewerPreservingView();
    return;
  }

  const scene = tour?.scenes?.[sceneId];
  if (!scene || !Array.isArray(scene.hotSpots)) {
    return;
  }

  scene.hotSpots.forEach((_spot, hotspotIndex) => {
    syncHotspotInViewer(sceneId, hotspotIndex);
  });
}

function stopViewerDragGesture() {
  if (!viewer) {
    return;
  }

  if (typeof viewer.stopMovement === "function") {
    viewer.stopMovement();
  }

  // Re-apply the current camera state to flush any pending drag momentum.
  if (
    typeof viewer.getPitch === "function" &&
    typeof viewer.getYaw === "function" &&
    typeof viewer.getHfov === "function" &&
    typeof viewer.lookAt === "function"
  ) {
    viewer.lookAt(viewer.getPitch(), viewer.getYaw(), viewer.getHfov(), false);
  }
}

function updateHotspotModeButtons() {
  const isAddMode = hotspotPanelMode === "add";
  const isMoveMode = hotspotPanelMode === "move";
  const isDeleteMode = hotspotPanelMode === "delete";

  if (el.hotspotModeAddButton) {
    el.hotspotModeAddButton.classList.toggle("is-active", isAddMode);
  }
  if (el.hotspotModeMoveButton) {
    el.hotspotModeMoveButton.classList.toggle("is-active", isMoveMode);
  }
  if (el.hotspotModeDeleteButton) {
    el.hotspotModeDeleteButton.classList.toggle("is-active", isDeleteMode);
  }
  if (el.hotspotAddForm) {
    el.hotspotAddForm.classList.toggle("is-hidden", !isAddMode);
  }
  if (el.placeHotspotButton) {
    const placing = Boolean(pendingHotspotPlacement);
    el.placeHotspotButton.textContent = placing ? "Cancel Viewer Placement" : "Place Hotspot In Viewer";
    el.placeHotspotButton.classList.toggle("is-active", placing);
  }
}

function cancelHotspotPlacement() {
  pendingHotspotPlacement = null;
  document.body.classList.remove("is-placing-hotspot");
  hideViewerCursorIndicator();
  updateHotspotModeButtons();
}

function beginHotspotPlacement(source) {
  pendingHotspotPlacement = { source };
  document.body.classList.add("is-placing-hotspot");
  updateHotspotModeButtons();
}

function setHotspotMoveMode(enabled) {
  hotspotMoveMode = Boolean(enabled);
  if (!hotspotMoveMode) {
    finishHotspotMove("");
  }
  document.body.classList.toggle("is-moving-hotspots", hotspotMoveMode);
  updateHotspotModeButtons();
  refreshHotspotInteractivityInViewer();
}

function setHotspotDeleteMode(enabled) {
  hotspotDeleteMode = Boolean(enabled);
  document.body.classList.toggle("is-deleting-hotspots", hotspotDeleteMode);
  updateHotspotModeButtons();
  refreshHotspotInteractivityInViewer();
}

function setHotspotPanelMode(mode) {
  const normalized = ["add", "move", "delete", "none"].includes(mode) ? mode : "none";
  hotspotPanelMode = normalized;

  if (normalized !== "add" && pendingHotspotPlacement) {
    cancelHotspotPlacement();
  }

  if (normalized === "move") {
    setHotspotDeleteMode(false);
    setHotspotMoveMode(true);
  } else if (normalized === "delete") {
    setHotspotMoveMode(false);
    setHotspotDeleteMode(true);
  } else {
    setHotspotMoveMode(false);
    setHotspotDeleteMode(false);
  }

  updateHotspotModeButtons();
}

function buildHotspotEntry(source, pitch, yaw) {
  const kind = el.hotspotKind.value;
  const target = el.hotspotTarget.value;
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
    throw new Error("Source scene must exist.");
  }

  if (Number.isNaN(pitch) || Number.isNaN(yaw)) {
    throw new Error("Pitch and yaw must be numeric.");
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
    const subplotColors = subplotConfigs.map((item, index) => {
      const candidate = String(item.color || "").toLowerCase();
      if (SUBPLOT_COLOR_OPTIONS.some((option) => option.value === candidate)) {
        return candidate;
      }
      return SUBPLOT_COLOR_OPTIONS[index % SUBPLOT_COLOR_OPTIONS.length].value;
    });
    const invertedBars = subplotConfigs.map((item) => Boolean(item.invertBar));
    const animate = el.hotspotAnimate.value === "true";
    const animationSpeed = DEFAULT_GRAPH_SECONDS_PER_FRAME;

    if (!csv || yColumns.length !== subplotCount || subplotTypes.length !== subplotCount) {
      throw new Error("Graph hotspots require CSV plus one Y column per subplot.");
    }

    return {
      spot: {
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
          subplotColors,
          invertedBars,
          animate,
          animationSpeed,
          size: "m",
        },
      },
      message: `Added graph hotspot in '${source}'.`,
      clear: "csv",
    };
  }

  if (kind === "image") {
    const fileName = el.hotspotImageFile.value.trim();
    const caption = el.hotspotImageCaption.value.trim();
    if (!fileName) {
      throw new Error("Image hotspots require an image file.");
    }

    return {
      spot: {
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
      },
      message: `Added image hotspot in '${source}'.`,
      clear: "image",
    };
  }

  if (kind === "text") {
    const freeText = el.hotspotFreeText.value.trim();
    if (!freeText) {
      throw new Error("Free text hotspots require text content.");
    }

    return {
      spot: {
        kind: "text",
        pitch,
        yaw,
        text,
        prompt: freeText,
      },
      message: `Added free text hotspot in '${source}'.`,
      clear: "none",
    };
  }

  if (!tour.scenes[target]) {
    throw new Error("Target scene must exist for navigation hotspots.");
  }

  return {
    spot: {
      kind: "scene",
      pitch,
      yaw,
      targetScene: target,
      text,
      prompt: text,
    },
    message: `Added hotspot in '${source}' to '${target}'.`,
    clear: "none",
  };
}

function addHotspotToScene(source, pitch, yaw) {
  const built = buildHotspotEntry(source, pitch, yaw);
  built.spot.id = nextHotspotId();
  tour.scenes[source].hotSpots.push(built.spot);
  if (built.clear === "csv") {
    el.csvUploadResult.textContent = "";
  } else if (built.clear === "image") {
    el.hotspotImageResult.textContent = "";
  }
  updateHotspotPositionFields(source);
  setStatus(built.message);
  return built.spot;
}

function deleteHotspotFromScene(sceneId, hotspotIndex) {
  const scene = tour?.scenes?.[sceneId];
  if (!scene || !Array.isArray(scene.hotSpots)) {
    return false;
  }
  if (hotspotIndex < 0 || hotspotIndex >= scene.hotSpots.length) {
    return false;
  }

  scene.hotSpots.splice(hotspotIndex, 1);
  return true;
}

function suppressHotspotActivation(event) {
  if (!hotspotMoveMode && !hotspotDeleteMode) {
    return;
  }
  if (hotspotDeleteMode && event.type === "click") {
    // Let delete-mode click handlers run on the hotspot wrapper.
    return;
  }
  event.preventDefault();
  event.stopPropagation();
  if (typeof event.stopImmediatePropagation === "function") {
    event.stopImmediatePropagation();
  }
}

function finishHotspotMove(message = "") {
  if (!dragState) {
    return;
  }
  document.body.classList.remove("is-dragging-hotspot");
  document.removeEventListener("mousemove", handleHotspotMove, true);
  document.removeEventListener("mouseup", handleHotspotMoveEnd, true);
  dragState = null;
  if (message) {
    setStatus(message);
  }
}

function handleHotspotMove(event) {
  if (!dragState || !viewer) {
    return;
  }

  const deltaX = event.clientX - dragState.startClientX;
  const deltaY = event.clientY - dragState.startClientY;
  if (!dragState.didDrag && Math.hypot(deltaX, deltaY) < HOTSPOT_DRAG_THRESHOLD_PX) {
    return;
  }

  dragState.didDrag = true;
  event.preventDefault();
  event.stopPropagation();

  const coords = viewer.mouseEventToCoords(event);
  if (!Array.isArray(coords) || coords.length < 2) {
    return;
  }

  const spot = findHotspot(dragState.sceneId, dragState.hotspotIndex);
  if (!spot) {
    finishHotspotMove("Stopped hotspot move because the hotspot no longer exists.");
    return;
  }

  spot.pitch = Number(coords[0].toFixed(2));
  spot.yaw = Number(coords[1].toFixed(2));
  updateHotspotPositionFields(dragState.sceneId);
  if (!syncHotspotInViewer(dragState.sceneId, dragState.hotspotIndex)) {
    renderViewerPreservingView();
  }
}

function handleHotspotMoveEnd(event) {
  if (!dragState) {
    return;
  }
  if (dragState.didDrag) {
    event.preventDefault();
    event.stopPropagation();
    finishHotspotMove("Hotspot moved. Save the tour to persist it.");
    return;
  }
  finishHotspotMove("");
}

function attachHotspotMoveHandlers(wrap, hotSpotDiv, sceneId, hotspotIndex) {
  hotSpotDiv.addEventListener("click", suppressHotspotActivation, true);
  hotSpotDiv.addEventListener("mouseup", suppressHotspotActivation, true);
  hotSpotDiv.addEventListener("contextmenu", suppressHotspotActivation, true);
  wrap.addEventListener("contextmenu", (event) => {
    if (hotspotMoveMode) {
      event.preventDefault();
    }
  });
  wrap.addEventListener("mousedown", (event) => {
    if (!hotspotMoveMode || event.button !== 0 || !viewer || viewer.getScene() !== sceneId) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    dragState = {
      sceneId,
      hotspotIndex,
      startClientX: event.clientX,
      startClientY: event.clientY,
      didDrag: false,
    };
    document.body.classList.add("is-dragging-hotspot");
    document.addEventListener("mousemove", handleHotspotMove, true);
    document.addEventListener("mouseup", handleHotspotMoveEnd, true);
  });

  wrap.addEventListener("click", (event) => {
    if (!hotspotDeleteMode || hotspotMoveMode || event.button !== 0) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    if (typeof event.stopImmediatePropagation === "function") {
      event.stopImmediatePropagation();
    }

    if (!deleteHotspotFromScene(sceneId, hotspotIndex)) {
      setStatus("Unable to delete hotspot because it no longer exists.", true);
      return;
    }

    renderViewerPreservingView();
    setStatus("Hotspot deleted. Save the tour to persist changes.");
  }, true);
}

function toPannellumHotspot(spot) {
  const common = {
    id: spot.id,
    pitch: Number(spot.pitch || 0),
    yaw: Number(spot.yaw || 0),
    createTooltipFunc: createHotspotDom,
    createTooltipArgs: {
      interactive: hotspotMoveMode || hotspotDeleteMode,
      sceneId: spot.sceneId,
      hotspotIndex: spot.hotspotIndex,
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
    hotSpots: sourceHotspots.map((spot, hotspotIndex) =>
      toPannellumHotspot({ ...spot, sceneId: scene.id, hotspotIndex }),
    ),
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
  const viewerNode = viewer.getContainer();
  viewerNode.addEventListener("mousedown", (event) => {
    if (!pendingHotspotPlacement || !viewer) {
      return;
    }
    if (event.target.closest(".hotspot-wrap")) {
      return;
    }

    if (event.button !== 0) {
      return;
    }

    placementPointerState = {
      startX: event.clientX,
      startY: event.clientY,
      moved: false,
    };
  }, true);
  viewerNode.addEventListener("mousemove", (event) => {
    if (!placementPointerState) {
      return;
    }

    const deltaX = event.clientX - placementPointerState.startX;
    const deltaY = event.clientY - placementPointerState.startY;
    if (Math.hypot(deltaX, deltaY) >= HOTSPOT_DRAG_THRESHOLD_PX) {
      placementPointerState.moved = true;
    }
  }, true);
  viewerNode.addEventListener("mouseup", (event) => {
    if (!pendingHotspotPlacement || !viewer) {
      placementPointerState = null;
      return;
    }
    if (event.target.closest(".hotspot-wrap")) {
      placementPointerState = null;
      return;
    }

    const pointerState = placementPointerState;
    placementPointerState = null;
    if (!pointerState || pointerState.moved || event.button !== 0) {
      return;
    }

    const coords = viewer.mouseEventToCoords(event);
    if (!Array.isArray(coords) || coords.length < 2) {
      return;
    }

    const source = pendingHotspotPlacement.source;
    try {
      addHotspotToScene(source, Number(coords[0].toFixed(2)), Number(coords[1].toFixed(2)));
      const hotspotIndex = tour.scenes[source].hotSpots.length - 1;
      cancelHotspotPlacement();
      if (!syncHotspotInViewer(source, hotspotIndex)) {
        renderViewer(source);
      }
      if (viewer) {
        viewer.lookAt(Number(coords[0].toFixed(2)), Number(coords[1].toFixed(2)), viewer.getHfov(), false);
        // Ensure click-placement does not leave the panorama in an active drag state.
        window.requestAnimationFrame(() => {
          stopViewerDragGesture();
        });
      }
      setStatus("Hotspot placed in viewer. Save the tour to persist it.");
    } catch (error) {
      cancelHotspotPlacement();
      setStatus(error.message || "Failed to place hotspot.", true);
    }
  }, true);
}

function fillSceneSelects() {
  // Populate all scene dropdowns from the same scene id list.
  const ids = Object.keys(tour.scenes);
  const optionsHtml = ids.map((id) => `<option value="${id}">${id}</option>`).join("");

  el.sceneSelect.innerHTML = optionsHtml;
  el.hotspotTarget.innerHTML = optionsHtml;

  // Preselect the configured start scene for convenience.
  if (tour.meta?.startScene && ids.includes(tour.meta.startScene)) {
    el.sceneSelect.value = tour.meta.startScene;
  } else if (ids.length > 0) {
    el.sceneSelect.value = ids[0];
  }

  syncHotspotSourceSelection();
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
  syncHotspotSourceSelection();
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

function clearPublishStatusPollTimer() {
  if (publishStatusPollTimer !== null) {
    window.clearInterval(publishStatusPollTimer);
    publishStatusPollTimer = null;
  }
}

async function pollPublishJob(statusUrl) {
  clearPublishStatusPollTimer();

  const pollOnce = async () => {
    const response = await fetch(statusUrl);
    const body = await response.json();
    if (!response.ok || !body.ok) {
      throw new Error(body.error || "Failed to read publish progress.");
    }

    const percent = Number.isFinite(Number(body.progress)) ? Math.max(0, Math.min(100, Number(body.progress))) : 0;
    const message = String(body.message || "Publishing...").trim();
    setPublishStatus(`Publishing static package to GitHub... ${percent}% - ${message}`);

    if (body.status === "completed") {
      clearPublishStatusPollTimer();
      return { done: true, body };
    }
    if (body.status === "failed") {
      clearPublishStatusPollTimer();
      throw new Error(body.error || "Publish failed.");
    }
    return { done: false, body };
  };

  const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

  while (true) {
    try {
      const result = await pollOnce();
      if (result.done) {
        clearPublishStatusPollTimer();
        return result.body;
      }
    } catch (error) {
      clearPublishStatusPollTimer();
      throw error;
    }

    await sleep(1000);
  }
}

function toggleViewerPlacement() {
  const source = getActiveViewerSceneId();
  if (!tour.scenes[source]) {
    setStatus("Source scene must exist before placing a hotspot.", true);
    return;
  }

  if (pendingHotspotPlacement) {
    cancelHotspotPlacement();
    setStatus("Viewer hotspot placement cancelled.");
    return;
  }

  try {
    buildHotspotEntry(source, 0, 0);
  } catch (error) {
    setStatus(error.message || "Hotspot details are incomplete.", true);
    return;
  }

  beginHotspotPlacement(source);
  if (viewer && viewer.getScene() !== source) {
    viewer.loadScene(source);
  }
  setStatus("Click the panorama to place the hotspot.");
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
  el.placeHotspotButton.addEventListener("click", toggleViewerPlacement);
  el.hotspotModeAddButton.addEventListener("click", () => {
    const nextMode = hotspotPanelMode === "add" ? "none" : "add";
    setHotspotPanelMode(nextMode);
    if (nextMode === "add") {
      setStatus("Hotspot add mode enabled. Configure details then click Place Hotspot In Viewer.");
    } else {
      setStatus("Hotspot add mode disabled.");
    }
  });

  el.hotspotModeMoveButton.addEventListener("click", () => {
    const nextMode = hotspotPanelMode === "move" ? "none" : "move";
    setHotspotPanelMode(nextMode);
    if (nextMode === "move") {
      setStatus("Hotspot move mode enabled. Left-drag a hotspot to move it.");
    } else {
      setStatus("Hotspot move mode disabled.");
    }
  });

  el.hotspotModeDeleteButton.addEventListener("click", () => {
    const nextMode = hotspotPanelMode === "delete" ? "none" : "delete";
    setHotspotPanelMode(nextMode);
    if (nextMode === "delete") {
      setStatus("Hotspot delete mode enabled. Click a hotspot to remove it.");
    } else {
      setStatus("Hotspot delete mode disabled.");
    }
  });

  el.refreshTours.addEventListener("click", async () => {
    try {
      await refreshTourList(resolveLoadTourName(), activeTourName);
      setStatus("Tour list refreshed.");
    } catch (_error) {
      setStatus("Failed to refresh tour list.", true);
    }
  });

  el.saveTourSelect.addEventListener("change", async () => {
    updateSaveTourUI();
    const targetTour = resolveWriteTourName();
    try {
      await refreshImageList("", "", targetTour);
      await refreshCsvSelects("", "", [], targetTour);
      updateSceneUploadUI();
      updateHotspotModeUI();
    } catch (_error) {
      // Keep UI usable even if tour-scoped list refresh fails.
    }
  });

  el.hotspotKind.addEventListener("change", updateHotspotModeUI);
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
    syncHotspotSourceSelection();
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

    // Scene objects use the same shape as persisted static/tours/<tour_name>.json.
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
    data.append("tour", resolveWriteTourName());

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
      await refreshImageList(body.filename, "", body.tour || resolveWriteTourName());
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
    data.append("tour", resolveWriteTourName());

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
      await refreshImageList("", body.filename, body.tour || resolveWriteTourName());
      updateHotspotModeUI();
    } catch (_error) {
      setStatus("Image uploaded, but failed to refresh image list.", true);
    }
    setStatus("Image upload complete. Selected for image hotspot.");
  });

  // Capture current camera view for precise hotspot placement.
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
    ensureHotspotIds();

    fillSceneSelects();
    renderViewer();
    try {
      await refreshTourList(loadedName, loadedName);
      await refreshImageList("");
      await refreshCsvSelects();
    } catch (_error) {
      // Load is complete; tour list refresh failure is non-fatal.
    }
    const removedStaleGraphs = Number(body.removedStaleGraphs || 0);
    if (removedStaleGraphs > 0) {
      setStatus(
        `Tour '${loadedName}' loaded from disk. Cleared ${removedStaleGraphs} stale cached graphs (renderer/settings changed).`,
      );
    } else {
      setStatus(`Tour '${loadedName}' loaded from disk. Graph cache reused.`);
    }
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
    ensureHotspotIds();

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
    const removedGraphs = Number(body.removedGraphs || 0);
    if (removedGraphs > 0) {
      setStatus(`Closed tour '${body.closed || "tour"}' and cleared ${removedGraphs} stale cached graphs.`);
    } else {
      setStatus(`Closed tour '${body.closed || "tour"}'. Graph cache preserved for faster reopen.`);
    }
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
    data.append("tour", resolveWriteTourName());

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
      await refreshCsvSelects(body.filename, "", [], body.tour || resolveWriteTourName());
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
    el.publishTourButton.disabled = true;

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

      if (response.status === 202 && body.jobId && body.statusUrl) {
        const finalJob = await pollPublishJob(body.statusUrl);
        const result = finalJob.result || {};
        const tours = Array.isArray(result.exported) ? result.exported.join(", ") : "";
        const destination = result.pagesUrl || result.repoUrl || `${owner}/${result.repo || body.repo || ""}`;
        let publishMessage = `Published ${tours} to ${destination}.`;
        if (result.pagesWarning) {
          publishMessage += ` ${result.pagesWarning}`;
        }
        setPublishStatus(publishMessage, false);
        setStatus("GitHub publish completed.");
        return;
      }

      const tours = Array.isArray(body.exported) ? body.exported.join(", ") : "";
      const destination = body.pagesUrl || body.repoUrl || `${owner}/${body.repo}`;
      let publishMessage = `Published ${tours} to ${destination}.`;
      if (body.pagesWarning) {
        publishMessage += ` ${body.pagesWarning}`;
      }
      setPublishStatus(publishMessage, false);
      setStatus("GitHub publish completed.");
    } catch (_error) {
      setPublishStatus("Publish request failed.", true);
    } finally {
      // Do not keep tokens in the form after a request completes.
      el.publishToken.value = "";
      el.publishTourButton.disabled = false;
      clearPublishStatusPollTimer();
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
    ensureHotspotIds();

    fillSceneSelects();
    renderViewer();
    await refreshTourList("", "");
    await refreshImageList("");
    await refreshCsvSelects();
    updateHotspotModeButtons();
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
