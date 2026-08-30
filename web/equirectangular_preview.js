import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import {
    DEFAULT_VIEW,
    MAX_FOV,
    MAX_PITCH,
    MIN_FOV,
    MIN_PITCH,
    PanoramaRenderer,
    clamp,
    degrees,
    normalizeYaw,
} from "./panorama_renderer.js";

const NODE_CLASS = "EquirectangularPreview";
const MIN_VIEWER_WIDTH = 220;
const MIN_VIEWER_HEIGHT = 140;
const DEFAULT_NODE_HEIGHT = 340;
const VIEWER_HORIZONTAL_PADDING = 20;
const VIEWER_BOTTOM_PADDING = 18;
const FALLBACK_VIEWER_TOP = 48;
const VIEW_STATE_WIDGETS = ["view_yaw", "view_pitch", "view_fov"];

function hideViewStateWidgets(node) {
    for (const name of VIEW_STATE_WIDGETS) {
        const widget = node.widgets?.find((candidate) => candidate.name === name);
        if (widget) {
            widget.hidden = true;
            widget.computeSize = () => [0, 0];
        }
    }
}

function getAvailableViewerWidth(node, size = node.size) {
    return Math.max(
        MIN_VIEWER_WIDTH,
        Math.round((size?.[0] ?? MIN_VIEWER_WIDTH + VIEWER_HORIZONTAL_PADDING) - VIEWER_HORIZONTAL_PADDING),
    );
}

function getAvailableViewerHeight(node, size = node.size) {
    const widgetTop = node.__equirectangularWidget?.last_y;
    const top = Number.isFinite(widgetTop) && widgetTop > 0
        ? widgetTop
        : FALLBACK_VIEWER_TOP;
    return Math.max(
        MIN_VIEWER_HEIGHT,
        Math.round((size?.[1] ?? DEFAULT_NODE_HEIGHT) - top - VIEWER_BOTTOM_PADDING),
    );
}

function imageUrl(image) {
    const params = new URLSearchParams({
        filename: image.filename,
        type: image.type ?? "temp",
        rand: String(Math.random()),
    });
    if (image.subfolder) {
        params.set("subfolder", image.subfolder);
    }
    return api.apiURL(`/view?${params.toString()}`);
}

function makeButton(label, title) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.title = title;
    button.style.cssText = [
        "height:24px",
        "padding:0 8px",
        "border:1px solid #555",
        "border-radius:4px",
        "background:#2b2b32",
        "color:#ddd",
        "font:11px sans-serif",
        "cursor:pointer",
        "pointer-events:auto",
    ].join(";");
    return button;
}

function createViewer(node) {
    const container = document.createElement("div");
    container.style.cssText = [
        "width:100%",
        `height:${MIN_VIEWER_HEIGHT}px`,
        `min-height:${MIN_VIEWER_HEIGHT}px`,
        "box-sizing:border-box",
        "display:flex",
        "flex-direction:column",
        "overflow:hidden",
        "border:1px solid #494951",
        "border-radius:6px",
        "background:#0e0e12",
        "pointer-events:auto",
    ].join(";");

    const toolbar = document.createElement("div");
    toolbar.style.cssText = [
        "height:32px",
        "box-sizing:border-box",
        "display:flex",
        "align-items:center",
        "gap:6px",
        "padding:4px 6px",
        "background:#202027",
        "border-bottom:1px solid #414149",
        "pointer-events:auto",
    ].join(";");

    const status = document.createElement("span");
    status.style.cssText = "flex:1;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;color:#bdbdc7;font:11px sans-serif;";
    status.textContent = "Run the workflow to load a panorama";

    const previous = makeButton("‹", "Previous image in batch");
    const next = makeButton("›", "Next image in batch");
    const reset = makeButton("Reset", "Reset yaw, pitch, and field of view");
    const fullscreen = makeButton("⛶", "Enter fullscreen");
    fullscreen.setAttribute("aria-label", "Enter fullscreen");
    fullscreen.setAttribute("aria-pressed", "false");
    previous.style.display = "none";
    next.style.display = "none";
    toolbar.append(status, previous, next, reset, fullscreen);

    const canvas = document.createElement("canvas");
    canvas.style.cssText = [
        "display:block",
        "width:100%",
        "height:calc(100% - 32px)",
        "min-height:0",
        "background:#0e0e12",
        "cursor:grab",
        "touch-action:none",
        "pointer-events:auto",
    ].join(";");
    container.append(toolbar, canvas);

    let renderer;
    try {
        renderer = new PanoramaRenderer(canvas);
    } catch (error) {
        console.error("[PepeUtils Equirectangular Preview]", error);
        status.textContent = error.message;
        status.style.color = "#ff8a80";
    }

    const stored = node.properties?.equirectangular_view ?? {};
    const view = {
        yaw: Number.isFinite(stored.yaw) ? stored.yaw : DEFAULT_VIEW.yaw,
        pitch: Number.isFinite(stored.pitch) ? stored.pitch : DEFAULT_VIEW.pitch,
        fov: Number.isFinite(stored.fov) ? stored.fov : DEFAULT_VIEW.fov,
    };
    let images = [];
    let imageIndex = 0;
    let loadVersion = 0;
    let dragging = false;
    let pointerX = 0;
    let pointerY = 0;
    let normalWidth = MIN_VIEWER_WIDTH;
    let normalHeight = MIN_VIEWER_HEIGHT;
    let drawFrame = 0;
    let persistTimer = 0;
    let destroyed = false;

    function syncViewWidgets() {
        const values = {
            view_yaw: degrees(view.yaw),
            view_pitch: degrees(view.pitch),
            view_fov: view.fov,
        };
        for (const [name, value] of Object.entries(values)) {
            const widget = node.widgets?.find((candidate) => candidate.name === name);
            if (widget) {
                widget.value = value;
            }
        }
    }

    function restoreView() {
        const storedView = node.properties?.equirectangular_view ?? {};
        const widgetValue = (name, fallback) => {
            const value = Number(node.widgets?.find((candidate) => candidate.name === name)?.value);
            return Number.isFinite(value) ? value : fallback;
        };
        view.yaw = Number.isFinite(storedView.yaw)
            ? storedView.yaw
            : widgetValue("view_yaw", degrees(DEFAULT_VIEW.yaw)) * Math.PI / 180;
        view.pitch = Number.isFinite(storedView.pitch)
            ? storedView.pitch
            : widgetValue("view_pitch", degrees(DEFAULT_VIEW.pitch)) * Math.PI / 180;
        view.fov = Number.isFinite(storedView.fov)
            ? storedView.fov
            : widgetValue("view_fov", DEFAULT_VIEW.fov);
        syncViewWidgets();
        draw();
    }

    function persistView() {
        node.properties ??= {};
        node.properties.equirectangular_view = { ...view };
        syncViewWidgets();
    }

    function persistViewSoon() {
        globalThis.clearTimeout(persistTimer);
        persistTimer = globalThis.setTimeout(() => {
            persistTimer = 0;
            if (!destroyed) {
                persistView();
            }
        }, 150);
    }

    function updateStatus(extra = "") {
        if (!renderer) {
            return;
        }
        const batch = images.length > 1 ? ` · ${imageIndex + 1}/${images.length}` : "";
        const suffix = extra ? ` · ${extra}` : "";
        status.textContent = `Yaw ${degrees(view.yaw).toFixed(0)}° · Pitch ${degrees(view.pitch).toFixed(0)}° · FOV ${view.fov.toFixed(0)}°${batch}${suffix}`;
        status.style.color = "#bdbdc7";
    }

    function drawNow() {
        drawFrame = 0;
        if (destroyed) {
            return;
        }
        renderer?.render(view);
        updateStatus();
    }

    function draw() {
        if (!drawFrame && !destroyed) {
            drawFrame = globalThis.requestAnimationFrame(drawNow);
        }
    }

    async function loadImageAt(index) {
        if (!renderer || !images.length) {
            return;
        }
        imageIndex = (index + images.length) % images.length;
        const version = ++loadVersion;
        updateStatus("Loading…");
        const image = new Image();
        image.onload = () => {
            if (version !== loadVersion) {
                return;
            }
            try {
                renderer.setImage(image);
                draw();
            } catch (error) {
                console.error("[PepeUtils Equirectangular Preview]", error);
                status.textContent = `Could not render panorama: ${error.message}`;
                status.style.color = "#ff8a80";
            }
        };
        image.onerror = () => {
            if (version === loadVersion) {
                status.textContent = "Could not load the temporary preview image";
                status.style.color = "#ff8a80";
            }
        };
        image.src = imageUrl(images[imageIndex]);
    }

    function setImages(nextImages) {
        images = Array.isArray(nextImages) ? nextImages.filter((item) => item?.filename) : [];
        imageIndex = 0;
        const showBatch = images.length > 1;
        previous.style.display = showBatch ? "block" : "none";
        next.style.display = showBatch ? "block" : "none";
        if (!images.length) {
            status.textContent = "Run the workflow to load a panorama";
            return;
        }
        loadImageAt(0);
    }

    function resetView() {
        Object.assign(view, DEFAULT_VIEW);
        persistView();
        draw();
    }

    function updateFullscreenLayout() {
        const active = document.fullscreenElement === container;
        fullscreen.setAttribute("aria-pressed", String(active));
        fullscreen.setAttribute("aria-label", active ? "Exit fullscreen" : "Enter fullscreen");
        fullscreen.title = active ? "Exit fullscreen (Esc)" : "Enter fullscreen";
        container.style.width = active ? "100vw" : `${normalWidth}px`;
        container.style.height = active ? "100vh" : `${normalHeight}px`;
        container.style.borderRadius = active ? "0" : "6px";
        draw();
    }

    async function toggleFullscreen() {
        try {
            if (document.fullscreenElement === container) {
                await document.exitFullscreen();
            } else {
                await container.requestFullscreen();
            }
        } catch (error) {
            console.error("[PepeUtils Equirectangular Preview]", error);
            status.textContent = `Could not toggle fullscreen: ${error.message}`;
            status.style.color = "#ff8a80";
        }
    }

    canvas.addEventListener("pointerdown", (event) => {
        if (event.button !== 0) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        dragging = true;
        pointerX = event.clientX;
        pointerY = event.clientY;
        canvas.style.cursor = "grabbing";
        canvas.setPointerCapture?.(event.pointerId);
    });
    canvas.addEventListener("pointermove", (event) => {
        if (!dragging) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        const sensitivity = Math.PI / Math.max(canvas.clientHeight, 160);
        view.yaw = normalizeYaw(view.yaw - (event.clientX - pointerX) * sensitivity);
        view.pitch = clamp(view.pitch + (event.clientY - pointerY) * sensitivity, MIN_PITCH, MAX_PITCH);
        pointerX = event.clientX;
        pointerY = event.clientY;
        syncViewWidgets();
        draw();
    });
    const endDrag = (event) => {
        if (!dragging) {
            return;
        }
        event?.preventDefault?.();
        event?.stopPropagation?.();
        dragging = false;
        persistView();
        canvas.style.cursor = "grab";
        if (event?.pointerId !== undefined) {
            canvas.releasePointerCapture?.(event.pointerId);
        }
    };
    canvas.addEventListener("pointerup", endDrag);
    canvas.addEventListener("pointercancel", endDrag);
    canvas.addEventListener("lostpointercapture", endDrag);
    canvas.addEventListener("wheel", (event) => {
        event.preventDefault();
        event.stopPropagation();
        view.fov = clamp(view.fov + event.deltaY * 0.04, MIN_FOV, MAX_FOV);
        syncViewWidgets();
        persistViewSoon();
        draw();
    }, { passive: false });
    canvas.addEventListener("contextmenu", (event) => event.preventDefault());

    previous.addEventListener("click", (event) => {
        event.stopPropagation();
        loadImageAt(imageIndex - 1);
    });
    next.addEventListener("click", (event) => {
        event.stopPropagation();
        loadImageAt(imageIndex + 1);
    });
    reset.addEventListener("click", (event) => {
        event.stopPropagation();
        resetView();
    });
    fullscreen.addEventListener("click", (event) => {
        event.stopPropagation();
        toggleFullscreen();
    });
    document.addEventListener("fullscreenchange", updateFullscreenLayout);

    const resizeObserver = new ResizeObserver(draw);
    resizeObserver.observe(canvas);
    syncViewWidgets();

    return {
        container,
        setImages,
        draw,
        restoreView,
        resize(width, height) {
            normalWidth = Math.max(MIN_VIEWER_WIDTH, Math.round(width));
            normalHeight = Math.max(MIN_VIEWER_HEIGHT, Math.round(height));
            if (document.fullscreenElement !== container) {
                container.style.width = `${normalWidth}px`;
                container.style.height = `${normalHeight}px`;
            }
            draw();
        },
        destroy() {
            destroyed = true;
            loadVersion += 1;
            globalThis.cancelAnimationFrame(drawFrame);
            globalThis.clearTimeout(persistTimer);
            document.removeEventListener("fullscreenchange", updateFullscreenLayout);
            if (document.fullscreenElement === container) {
                document.exitFullscreen().catch(() => {});
            }
            resizeObserver.disconnect();
            renderer?.destroy();
            container.remove();
        },
    };
}

app.registerExtension({
    name: "pepeutils.equirectangular_preview",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_CLASS) {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);
            const viewer = createViewer(this);
            this.__equirectangularViewer = viewer;
            const widget = this.addDOMWidget("equirectangular_preview", "equirectangular_preview", viewer.container, {
                serialize: false,
                hideOnZoom: false,
            });
            this.__equirectangularWidget = widget;
            hideViewStateWidgets(this);
            widget.computeSize = () => [MIN_VIEWER_WIDTH, MIN_VIEWER_HEIGHT];
            this.setSize([
                Math.max(this.size?.[0] ?? 0, 340),
                Math.max(this.size?.[1] ?? 0, DEFAULT_NODE_HEIGHT),
            ]);
            viewer.resize(
                getAvailableViewerWidth(this),
                getAvailableViewerHeight(this),
            );
            return result;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const result = onExecuted?.apply(this, arguments);
            this.imgs = [];
            this.imageIndex = null;
            this.previewMediaType = undefined;
            this.__equirectangularViewer?.setImages(message?.images ?? []);
            return result;
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = onConfigure?.apply(this, arguments);
            hideViewStateWidgets(this);
            this.__equirectangularViewer?.restoreView();
            return result;
        };

        // ComfyUI installs its flat image renderer on output-node backgrounds.
        // This node owns the preview surface, so do not draw the duplicate native view.
        nodeType.prototype.onDrawBackground = function () {
            this.imgs = [];
            this.imageIndex = null;
            this.overIndex = null;
            this.previewMediaType = undefined;
        };

        const onResize = nodeType.prototype.onResize;
        nodeType.prototype.onResize = function (size) {
            const result = onResize?.apply(this, arguments);
            const nextSize = size ?? this.size;
            this.__equirectangularViewer?.resize(
                getAvailableViewerWidth(this, nextSize),
                getAvailableViewerHeight(this, nextSize),
            );
            return result;
        };

        const onRemoved = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            this.__equirectangularViewer?.destroy();
            delete this.__equirectangularViewer;
            delete this.__equirectangularWidget;
            return onRemoved?.apply(this, arguments);
        };
    },
});
