let viewer = null;
let activeTourName = "";
let tour = null;
let isSingleTourMode = false;

const el = {
  tourSelect: document.getElementById("tour-select"),
  refreshTours: document.getElementById("refresh-tours"),
  loadTour: document.getElementById("load-tour"),
  status: document.getElementById("status"),
};

function applySingleTourMode(enabled) {
  isSingleTourMode = Boolean(enabled);
  document.body.classList.toggle("single-tour-mode", isSingleTourMode);

  const layout = document.querySelector(".layout");
  const panel = document.querySelector(".panel");
  const viewerWrap = document.querySelector(".viewer-wrap");
  const brand = document.querySelector(".viewer-brand");
  const viewerNode = document.getElementById("viewer");

  if (isSingleTourMode) {
    if (layout) {
      layout.style.gridTemplateColumns = "1fr";
    }
    if (panel) {
      panel.style.display = "none";
    }
    if (viewerWrap) {
      viewerWrap.style.display = "grid";
      viewerWrap.style.gridTemplateRows = "auto 1fr";
      viewerWrap.style.gap = "8px";
      viewerWrap.style.padding = "10px";
      viewerWrap.style.border = "4px solid rgba(28, 42, 34, 0.72)";
      viewerWrap.style.background = "rgba(17, 24, 19, 0.72)";
      viewerWrap.style.boxShadow = "0 10px 28px rgba(13, 22, 18, 0.28)";
    }
    if (brand) {
      brand.style.display = "block";
      brand.style.position = "relative";
      brand.style.top = "auto";
      brand.style.left = "auto";
      brand.style.margin = "0";
    }
    if (viewerNode) {
      viewerNode.style.height = "100%";
      viewerNode.style.minHeight = "0";
      viewerNode.style.borderRadius = "12px";
      viewerNode.style.overflow = "hidden";
    }
    return;
  }

  if (layout) {
    layout.style.gridTemplateColumns = "";
  }
  if (panel) {
    panel.style.display = "";
  }
  if (viewerWrap) {
    viewerWrap.style.display = "";
    viewerWrap.style.gridTemplateRows = "";
    viewerWrap.style.gap = "";
    viewerWrap.style.padding = "";
    viewerWrap.style.border = "";
    viewerWrap.style.background = "";
    viewerWrap.style.boxShadow = "";
  }
  if (brand) {
    brand.style.display = "";
    brand.style.position = "";
    brand.style.top = "";
    brand.style.left = "";
    brand.style.margin = "";
  }
  if (viewerNode) {
    viewerNode.style.height = "";
    viewerNode.style.minHeight = "";
    viewerNode.style.borderRadius = "";
    viewerNode.style.overflow = "";
  }
}

function setStatus(msg, isError = false) {
  el.status.textContent = msg;
  el.status.style.color = isError ? "#ffd0d0" : "#d8ffe0";
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(value, max));
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
      prompt.appendChild(graphContainer);

      let lastQueryKey = "";
      const resetGraphPreview = () => {
        lastQueryKey = "";
        graphContainer.replaceChildren();
        graphContainer.textContent = "Loading graph...";
      };

      const graphPath = String(args.graph.path || "").trim();
      wrap.addEventListener("mouseenter", () => {
        positionPromptCard(wrap, prompt);
        if (!graphPath) {
          graphContainer.textContent = "No pre-rendered graph asset found.";
          return;
        }
        if (graphContainer.querySelector("img")) {
          return;
        }
        graphContainer.replaceChildren();
        const img = document.createElement("img");
        img.className = "graph-preview";
        img.alt = "Pre-rendered graph";
        img.src = `${graphPath}?t=${Date.now()}`;
        img.addEventListener("load", () => {
          positionPromptCard(wrap, prompt);
        });
        graphContainer.appendChild(img);
      });
      wrap.addEventListener("mouseleave", () => {
        resetGraphPreview();
      });
    } else if (kind === "image" && args.image) {
      prompt.classList.add("prompt-card--image");
      prompt.style.setProperty("--image-card-width", "680px");
      const imageContainer = document.createElement("div");
      imageContainer.className = "image-container";

      const imagePath = String(args.image.path || "").trim();
      if (imagePath) {
        const img = document.createElement("img");
        img.className = "image-preview";
        img.alt = "Hotspot image preview";
        img.src = imagePath;
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

function toPannellumSceneConfig(scene) {
  const sourceHotspots = Array.isArray(scene.hotSpots) ? scene.hotSpots : [];
  return {
    title: scene.title || scene.id,
    type: "equirectangular",
    panorama: scene.panorama,
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

async function fetchManifest() {
  const response = await fetch("published/tours.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Could not load published/tours.json.");
  }
  const body = await response.json();
  return Array.isArray(body.tours) ? body.tours : [];
}

async function fetchTour(name) {
  const response = await fetch(`published/tours/${encodeURIComponent(name)}/tour.json`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Could not load tour '${name}'.`);
  }
  return response.json();
}

function getTourFromQuery() {
  const params = new URLSearchParams(window.location.search);
  return (params.get("tour") || "").trim();
}

function updateQueryTour(name) {
  if (isSingleTourMode) {
    return;
  }
  const url = new URL(window.location.href);
  if (name) {
    url.searchParams.set("tour", name);
  } else {
    url.searchParams.delete("tour");
  }
  window.history.replaceState({}, "", url);
}

async function refreshTourList(preferred = "") {
  const tours = await fetchManifest();
  if (tours.length === 0) {
    el.tourSelect.innerHTML = "";
    renderEmpty("No published tours found. Run export_github_pages.py first.");
    setStatus("No published tours found.", true);
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
    setStatus("Select a tour first.", true);
    return;
  }

  try {
    tour = await fetchTour(name);
    activeTourName = name;
    if (!tour.meta) {
      tour.meta = {};
    }
    if (!tour.scenes) {
      tour.scenes = {};
    }
    renderViewer();
    updateQueryTour(name);
    setStatus(`Loaded tour '${name}'.`);
  } catch (error) {
    setStatus(error.message || "Failed to load selected tour.", true);
  }
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
}

async function boot() {
  try {
    renderEmpty("Loading published tours...");
    const requestedTour = getTourFromQuery();
    const tours = await refreshTourList(requestedTour);
    applySingleTourMode(tours.length === 1);
    setupEvents();
    if (tours.length > 0) {
      await loadSelectedTour();
    }
  } catch (_error) {
    setStatus("Failed to initialize viewer.", true);
    renderEmpty("Viewer initialization failed.");
  }
}

boot();
