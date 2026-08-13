let viewer = null;
let activeTourName = "";
let tour = null;
const SUBPLOT_COLOR_OPTIONS = [
  "red",
  "blue",
  "green",
  "orange",
  "purple",
  "teal",
  "brown",
  "black",
  "gray",
  "pink",
];

const el = {
  tourSelect: document.getElementById("tour-select"),
  refreshTours: document.getElementById("refresh-tours"),
  loadTour: document.getElementById("load-tour"),
  exitTour: document.getElementById("exit-tour"),
  status: document.getElementById("status"),
};

function setStage(stage) {
  document.body.dataset.stage = stage;
}

function setStatus(msg, isError = false) {
  el.status.textContent = msg;
  el.status.style.color = isError ? "#ffd0d0" : "#d8ffe0";
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(value, max));
}

function asTruthy(value) {
  if (value === true || value === 1) {
    return true;
  }
  const text = String(value || "").trim().toLowerCase();
  return text === "true" || text === "1" || text === "yes" || text === "on";
}

function getViewerMode() {
  return document.body?.dataset?.viewerMode === "published" ? "published" : "app";
}

function isPublishedViewerMode() {
  return getViewerMode() === "published";
}

function isTouchLikeInteraction() {
  if (typeof window.matchMedia === "function") {
    return window.matchMedia("(hover: none) and (pointer: coarse)").matches;
  }
  return Boolean(window.ontouchstart) || navigator.maxTouchPoints > 0;
}

function positionPromptCard(wrap, prompt) {
  const viewportPadding = 8;
  const gap = 24;
  const isMediaPrompt =
    prompt.classList.contains("prompt-card--graph") ||
    prompt.classList.contains("prompt-card--image");

  if (isTouchLikeInteraction()) {
    prompt.style.left = "50%";
    prompt.style.top = "-8px";
    prompt.style.transform = "translate(-50%, -100%)";
    return;
  }

  const wrapRect = wrap.getBoundingClientRect();
  const promptRect = prompt.getBoundingClientRect();
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  const viewerRect = document.getElementById("viewer")?.getBoundingClientRect();

  let left = gap;
  let top = 8;

  if (isMediaPrompt && viewerRect) {
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

  prompt.style.left = `${left}px`;
  prompt.style.top = `${top}px`;
}

function createHotspotDom(hotSpotDiv, args) {
  if (hotSpotDiv.querySelector(".hotspot-wrap")) {
    return;
  }

  const kind = args.kind || "scene";
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
    kind === "text" ||
    kind === "textLink"
  ) {
    const prompt = document.createElement("div");
    prompt.className = `prompt-card prompt-card--${kind}`;
    const promptText = document.createElement("div");
    const showPromptCard = () => {
      wrap.classList.add("is-active");
      positionPromptCard(wrap, prompt);
      prompt.classList.add("is-visible");
    };
    const hidePromptCard = () => {
      wrap.classList.remove("is-active");
      prompt.classList.remove("is-visible");
    };
    promptText.textContent =
      (kind === "text" || kind === "textLink" ? args.prompt || args.text : args.text || args.prompt) ||
      (kind === "graph"
        ? "Graphed data"
        : kind === "image"
          ? "Image preview"
          : kind === "textLink"
            ? "Open link"
            : "Free text");
    prompt.appendChild(promptText);

    if (kind === "textLink" && args.link && args.link.url) {
      wrap.classList.add("hotspot-wrap--link");
      wrap.title = "Open external link";
      wrap.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        const targetBehavior = args.link.target === "_self" ? "_self" : "_blank";
        window.open(args.link.url, targetBehavior, targetBehavior === "_blank" ? "noopener,noreferrer" : undefined);
      });
    }

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

      let lastQueryKey = "";
      const resetGraphPreview = () => {
        lastQueryKey = "";
        graphContainer.replaceChildren();
        graphContainer.textContent = "Loading graph...";
      };
      const loadGraphPreview = async () => {
        positionPromptCard(wrap, prompt);

        const graphPath = String(args.graph.path || "").trim();
        if (graphPath) {
          graphContainer.replaceChildren();
          const img = document.createElement("img");
          img.className = "graph-preview";
          img.alt = "Pre-rendered graph";
          img.src = `${graphPath}?t=${Date.now()}`;
          img.addEventListener("load", () => {
            positionPromptCard(wrap, prompt);
          });
          graphContainer.appendChild(img);
          return;
        }

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
        const yAxisLabels = Array.isArray(args.graph.yAxisLabels)
          ? args.graph.yAxisLabels.map((value) => String(value ?? "").trim())
          : [];

        const query = new URLSearchParams({
          name: activeTourName,
          csv: args.graph.csv || "",
          animate: String(args.graph.animate === true || args.graph.animate === "true"),
        });

        const subplots = Number.parseInt(args.graph.subplots, 10);
        const subplotCount = Number.isFinite(subplots) ? clamp(subplots, 1, 3) : clamp(yColumns.length || 1, 1, 3);
        query.set("subplots", String(subplotCount));
        yColumns.slice(0, subplotCount).forEach((columnName) => {
          query.append("y", columnName);
        });
        for (let idx = 0; idx < subplotCount; idx += 1) {
          query.append("plotType", subplotTypes[idx] || "line");
          query.append("color", subplotColors[idx] || SUBPLOT_COLOR_OPTIONS[idx % SUBPLOT_COLOR_OPTIONS.length]);
          query.append("invertBar", invertedBars[idx] ? "true" : "false");
          query.append("yAxisLabel", yAxisLabels[idx] || "");
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

        const queryKey = query.toString();
        if (queryKey === lastQueryKey && graphContainer.querySelector("img")) {
          return;
        }
        lastQueryKey = queryKey;
        graphContainer.textContent = "Loading graph...";

        try {
          if (isPublishedViewerMode()) {
            graphContainer.textContent = "Graph preview unavailable.";
            return;
          }

          const response = await fetch(`/api/viewer/graph?${query.toString()}`);
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
      };

      wrap.addEventListener("mouseenter", async () => {
        showPromptCard();
        await loadGraphPreview();
      });

      wrap.addEventListener("mouseleave", () => {
        resetGraphPreview();
        hidePromptCard();
      });
    } else if (kind === "image" && args.image) {
      prompt.classList.add("prompt-card--image");
      prompt.style.setProperty("--image-card-width", "680px");
      const imageContainer = document.createElement("div");
      imageContainer.className = "image-container";

      const imagePath =
        args.image.path || (args.image.file ? `/images2d/${activeTourName}/${args.image.file}` : "");
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
        showPromptCard();
      });
      wrap.addEventListener("mouseleave", () => {
        hidePromptCard();
      });
    } else {
      wrap.addEventListener("mouseenter", () => {
        showPromptCard();
      });
      wrap.addEventListener("mouseleave", () => {
        hidePromptCard();
      });
    }

    if (isTouchLikeInteraction() && kind !== "scene") {
      wrap.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (wrap.classList.contains("is-active")) {
          hidePromptCard();
          return;
        }
        showPromptCard();
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
      link: spot.link || null,
    },
  };

  if (spot.kind === "graph" || spot.kind === "image" || spot.kind === "text" || spot.kind === "textLink") {
    return {
      ...common,
      type: "info",
      text:
        spot.text ||
        (spot.kind === "graph"
          ? "Graphed data"
          : spot.kind === "image"
            ? "Image"
            : spot.kind === "textLink"
              ? "Open link"
              : "Free text"),
    };
  }

  return {
    ...common,
    type: "scene",
    text: spot.text || spot.targetScene || "Open",
    sceneId: spot.targetScene,
  };
}

// Partial panoramas (a 360 sweep missing sky/ground) need explicit coverage angles.
function toPanoramaCoverageConfig(scene) {
  const vaov = Number.parseFloat(scene.vaov);
  if (!Number.isFinite(vaov) || vaov <= 0 || vaov >= 180) {
    return {};
  }

  const haov = Number.parseFloat(scene.haov);
  const parsedOffset = Number.parseFloat(scene.vOffset);
  const vOffset = Number.isFinite(parsedOffset) ? parsedOffset : 0;

  // Pannellum maps the band correctly but still lets the view pan into empty space.
  return {
    haov: Number.isFinite(haov) && haov > 0 ? haov : 360,
    vaov,
    vOffset,
    minPitch: vOffset - (vaov / 2),
    maxPitch: vOffset + (vaov / 2),
  };
}

function toPannellumSceneConfig(scene) {
  const sourceHotspots = Array.isArray(scene.hotSpots) ? scene.hotSpots : [];
  return {
    title: scene.title || scene.id,
    type: "equirectangular",
    panorama: scene.panorama,
    ...toPanoramaCoverageConfig(scene),
    hotSpots: sourceHotspots.map((spot) => toPannellumHotspot(spot)),
  };
}

function renderEmpty(message) {
  const node = document.getElementById("viewer");
  node.innerHTML = `<div class="viewer-empty">${message}</div>`;
}

function renderViewer() {
  if (viewer) {
    viewer.destroy();
    viewer = null;
  }
  if (!tour?.scenes || Object.keys(tour.scenes).length === 0) {
    renderEmpty("Selected tour has no scenes.");
    return;
  }

  const scenesConfig = {};
  Object.values(tour.scenes).forEach((scene) => {
    scenesConfig[scene.id] = toPannellumSceneConfig(scene);
  });

  const fallbackFirstScene = tour.meta?.startScene || Object.keys(tour.scenes)[0];
  const config = {
    default: {
      firstScene: fallbackFirstScene,
      autoLoad: true,
      showControls: true,
      compass: false,
    },
    scenes: scenesConfig,
  };

  document.getElementById("viewer").innerHTML = "";
  viewer = pannellum.viewer("viewer", config);
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }
  return response.json();
}

async function fetchTours() {
  if (isPublishedViewerMode()) {
    const body = await fetchJson("published/tours.json");
    if (Array.isArray(body)) {
      return body;
    }
    if (Array.isArray(body.tours)) {
      return body.tours;
    }
    throw new Error(body.error || "Failed to fetch tours.");
  }

  const response = await fetch("/api/viewer/tours");
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Failed to fetch tours.");
  }
  return Array.isArray(body.tours) ? body.tours : [];
}

async function fetchTour(name) {
  if (isPublishedViewerMode()) {
    const body = await fetchJson(`published/tours/${encodeURIComponent(name)}/tour.json`);
    if (body && typeof body === "object" && body.error) {
      throw new Error(body.error);
    }
    return {
      name,
      tour: body || {},
    };
  }

  const query = new URLSearchParams({ name });
  const response = await fetch(`/api/viewer/tour?${query.toString()}`);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Failed to load selected tour.");
  }
  return body;
}

async function refreshTourList(preferred = "") {
  const tours = await fetchTours();
  if (tours.length === 0) {
    el.tourSelect.innerHTML = "";
    setStatus("No saved tours found.", true);
    return [];
  }

  el.tourSelect.innerHTML = tours.map((name) => `<option value="${name}">${name}</option>`).join("");
  const selected = preferred && tours.includes(preferred) ? preferred : tours[0];
  el.tourSelect.value = selected;
  return tours;
}

async function loadSelectedTour() {
  const name = (el.tourSelect.value || "").trim();
  if (!name) {
    setStatus("Select a saved tour first.", true);
    return;
  }
  try {
    const payload = await fetchTour(name);
    activeTourName = payload.name || name;
    tour = payload.tour || {};
    if (!tour.meta) {
      tour.meta = {};
    }
    if (!tour.scenes) {
      tour.scenes = {};
    }
    // Pannellum needs a laid-out container, so reveal the stage before rendering.
    setStage("tour");
    renderViewer();
    setStatus(`Loaded tour '${activeTourName}'.`);
  } catch (error) {
    setStatus(error.message || "Failed to load selected tour.", true);
  }
}

function exitTour() {
  if (viewer) {
    viewer.destroy();
    viewer = null;
  }
  document.getElementById("viewer").innerHTML = "";
  setStage("select");
}

function setupEvents() {
  el.refreshTours.addEventListener("click", async () => {
    try {
      const preferred = el.tourSelect.value;
      const tours = await refreshTourList(preferred);
      if (tours.length > 0) {
        setStatus("Tour list refreshed.");
      }
    } catch (_error) {
      setStatus("Failed to refresh tour list.", true);
    }
  });

  el.loadTour.addEventListener("click", async () => {
    await loadSelectedTour();
  });

  el.exitTour.addEventListener("click", exitTour);
}

async function boot() {
  try {
    const tours = await refreshTourList();
    setupEvents();
    if (tours.length > 0) {
      setStatus("Select a tour and choose View Tour.");
    }
  } catch (_error) {
    setStatus("Failed to initialize viewer.", true);
  }
}

boot();