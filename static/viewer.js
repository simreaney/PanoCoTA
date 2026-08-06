let viewer = null;
let activeTourName = "";
let tour = null;

const el = {
  tourSelect: document.getElementById("tour-select"),
  refreshTours: document.getElementById("refresh-tours"),
  loadTour: document.getElementById("load-tour"),
  status: document.getElementById("status"),
};

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
    kind === "text"
  ) {
    const prompt = document.createElement("div");
    prompt.className = `prompt-card prompt-card--${kind}`;
    const promptText = document.createElement("div");
    promptText.textContent =
      (kind === "text" ? args.prompt || args.text : args.text || args.prompt) ||
      (kind === "graph" ? "Graphed data" : kind === "image" ? "Image preview" : "Free text");
    prompt.appendChild(promptText);

    if (kind === "graph" && args.graph) {
      prompt.classList.add("prompt-card--graph");
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
          name: activeTourName,
          csv: args.graph.csv || "",
          animate: String(args.graph.animate === true || args.graph.animate === "true"),
        });
        const speed = Number.parseFloat(args.graph.animationSpeed || "1");
        query.set("animationSpeed", String(Number.isFinite(speed) ? speed : 1));

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
      });
    } else if (kind === "image" && args.image) {
      prompt.classList.add("prompt-card--image");
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

async function fetchTours() {
  const response = await fetch("/api/viewer/tours");
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || "Failed to fetch tours.");
  }
  return Array.isArray(body.tours) ? body.tours : [];
}

async function fetchTour(name) {
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
    renderEmpty("No saved tours found. Create and save one in the editor first.");
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
    renderViewer();
    setStatus(`Loaded tour '${activeTourName}'.`);
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
    renderEmpty("Loading saved tours...");
    const tours = await refreshTourList();
    setupEvents();
    if (tours.length > 0) {
      await loadSelectedTour();
    }
  } catch (_error) {
    setStatus("Failed to initialize viewer.", true);
    renderEmpty("Unable to initialize viewer.");
  }
}

boot();