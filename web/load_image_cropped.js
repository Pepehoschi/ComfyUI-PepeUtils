import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "LoadImageCropped";
const HIDDEN_WIDGETS = ["x1", "y1", "x2", "y2"];
const BORDER_COLOR = "#6cf08a";
const INFO_HEIGHT = 22;
const DEFAULT_PREVIEW_HEIGHT = 220 + INFO_HEIGHT;
const MIN_PREVIEW_HEIGHT = 80 + INFO_HEIGHT;
const PREVIEW_BOTTOM_PADDING = 22;

function getWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name) ?? null;
}

function getCropWidgets(node) {
    return {
        x1: getWidget(node, "x1"),
        y1: getWidget(node, "y1"),
        x2: getWidget(node, "x2"),
        y2: getWidget(node, "y2"),
    };
}

function hideWidget(widget) {
    if (!widget || widget.__loadImageCroppedHidden) {
        return;
    }

    widget.__loadImageCroppedHidden = true;
    widget.computeSize = () => [0, 0];
    widget.hidden = true;
}

function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function getStoredCrop(node) {
    const widgets = getCropWidgets(node);
    if (!widgets.x1 || !widgets.y1 || !widgets.x2 || !widgets.y2) {
        return null;
    }

    return {
        x1: Number(widgets.x1.value ?? 0),
        y1: Number(widgets.y1.value ?? 0),
        x2: Number(widgets.x2.value ?? 0),
        y2: Number(widgets.y2.value ?? 0),
    };
}

function setStoredCrop(node, crop) {
    const widgets = getCropWidgets(node);
    for (const [key, value] of Object.entries(crop)) {
        const widget = widgets[key];
        if (!widget) {
            continue;
        }
        widget.value = Math.max(0, Math.round(value));
        widget.callback?.(widget.value);
    }
}

function hasValidCrop(crop) {
    return crop && crop.x1 !== crop.x2 && crop.y1 !== crop.y2;
}

function normalizeCrop(crop, width, height) {
    const left = Math.max(0, Math.min(Math.round(crop?.x1 ?? 0), Math.round(crop?.x2 ?? 0)));
    const top = Math.max(0, Math.min(Math.round(crop?.y1 ?? 0), Math.round(crop?.y2 ?? 0)));
    const right = Math.min(width, Math.max(Math.round(crop?.x1 ?? 0), Math.round(crop?.x2 ?? 0)));
    const bottom = Math.min(height, Math.max(Math.round(crop?.y1 ?? 0), Math.round(crop?.y2 ?? 0)));

    if (right <= left || bottom <= top) {
        return { left: 0, top: 0, right: width, bottom: height, width, height };
    }

    return {
        left,
        top,
        right,
        bottom,
        width: right - left,
        height: bottom - top,
    };
}

function getImageWidgetValue(node) {
    return getWidget(node, "image")?.value ?? null;
}

function isImageFile(file) {
    return !!file?.type?.startsWith?.("image/");
}

async function applyImageSelection(node, filename) {
    const imageWidget = getWidget(node, "image");
    if (!imageWidget || !filename) {
        return false;
    }

    if (Array.isArray(imageWidget.options?.values) && !imageWidget.options.values.includes(filename)) {
        imageWidget.options.values = [...imageWidget.options.values, filename].sort();
    }

    imageWidget.value = filename;
    imageWidget.callback?.(filename);
    node.__loadImageCroppedFilename = null;
    node.__loadImageCroppedImage = null;
    node.setDirtyCanvas(true, true);
    renderPreview(node);
    return true;
}

async function uploadImageFile(node, file) {
    if (!isImageFile(file)) {
        return false;
    }

    const body = new FormData();
    body.append("image", file, file.name);
    body.append("type", "input");

    const response = await api.fetchApi("/upload/image", {
        method: "POST",
        body,
    });

    if (response.status !== 200) {
        return false;
    }

    const data = await response.json();
    return applyImageSelection(node, data?.name ?? file.name);
}

function makeImageUrl(filename) {
    return api.apiURL(`/view?filename=${encodeURIComponent(filename)}&type=input`);
}

function ensurePreviewImage(node) {
    const filename = getImageWidgetValue(node);
    if (!filename) {
        node.__loadImageCroppedImage = null;
        node.__loadImageCroppedFilename = null;
        return;
    }

    if (node.__loadImageCroppedFilename === filename && node.__loadImageCroppedImage) {
        return;
    }

    const image = new Image();
    image.onload = () => renderPreview(node);
    image.onerror = () => {
        node.__loadImageCroppedImage = null;
        renderPreview(node);
    };

    node.__loadImageCroppedFilename = filename;
    node.__loadImageCroppedImage = image;
    image.src = makeImageUrl(filename);
}

function getCanvasRect(node) {
    const canvas = node.__loadImageCroppedPreviewCanvas;
    if (!canvas) {
        return null;
    }

    const width = canvas.clientWidth || 1;
    const height = canvas.clientHeight || 1;
    const image = node.__loadImageCroppedImage;
    if (!image || !image.width || !image.height) {
        return { x: 0, y: 0, width, height, imageWidth: 1, imageHeight: 1 };
    }

    const scale = Math.min(width / image.width, height / image.height);
    const drawWidth = image.width * scale;
    const drawHeight = image.height * scale;

    return {
        x: (width - drawWidth) / 2,
        y: (height - drawHeight) / 2,
        width: drawWidth,
        height: drawHeight,
        imageWidth: image.width,
        imageHeight: image.height,
    };
}

function localToImage(rect, pos) {
    const px = clamp((pos.x - rect.x) / rect.width, 0, 1);
    const py = clamp((pos.y - rect.y) / rect.height, 0, 1);
    return {
        x: Math.round(px * rect.imageWidth),
        y: Math.round(py * rect.imageHeight),
    };
}

function imageToLocal(rect, point) {
    const x = clamp(point.x, 0, rect.imageWidth);
    const y = clamp(point.y, 0, rect.imageHeight);
    return {
        x: rect.x + (x / rect.imageWidth) * rect.width,
        y: rect.y + (y / rect.imageHeight) * rect.height,
    };
}

function getPointerPos(canvas, event) {
    const bounds = canvas.getBoundingClientRect();
    const scaleX = bounds.width > 0 ? (canvas.clientWidth || 1) / bounds.width : 1;
    const scaleY = bounds.height > 0 ? (canvas.clientHeight || 1) / bounds.height : 1;
    return {
        x: (event.clientX - bounds.left) * scaleX,
        y: (event.clientY - bounds.top) * scaleY,
    };
}

function isInsideRect(rect, pos) {
    return (
        pos.x >= rect.x &&
        pos.x <= rect.x + rect.width &&
        pos.y >= rect.y &&
        pos.y <= rect.y + rect.height
    );
}

function getPreviewHeight(node) {
    return Math.max(
        MIN_PREVIEW_HEIGHT,
        Math.round(node.__loadImageCroppedPreviewHeight ?? DEFAULT_PREVIEW_HEIGHT),
    );
}

function getWidgetBottom(node) {
    let bottom = 0;
    for (const widget of node.widgets ?? []) {
        if (widget?.__loadImageCroppedHidden || widget?.name === "crop_preview") {
            continue;
        }
        bottom = Math.max(bottom, widget.last_y ?? 0);
    }
    return bottom;
}

function getAvailablePreviewHeight(node) {
    const widgetBottom = getWidgetBottom(node);
    const topPadding = LiteGraph.NODE_WIDGET_HEIGHT;
    const available =
        (node.size?.[1] ?? DEFAULT_PREVIEW_HEIGHT) -
        widgetBottom -
        topPadding -
        PREVIEW_BOTTOM_PADDING;
    return Math.max(MIN_PREVIEW_HEIGHT, Math.round(available));
}

function setPreviewHeight(node, height) {
    const nextHeight = Math.max(MIN_PREVIEW_HEIGHT, Math.round(height));
    if (node.__loadImageCroppedPreviewHeight === nextHeight) {
        return;
    }
    node.__loadImageCroppedPreviewHeight = nextHeight;
    node.setDirtyCanvas(true, true);
}

function drawCrop(ctx, rect, crop) {
    if (!hasValidCrop(crop)) {
        return;
    }

    const start = imageToLocal(rect, { x: crop.x1, y: crop.y1 });
    const end = imageToLocal(rect, { x: crop.x2, y: crop.y2 });
    const left = Math.min(start.x, end.x);
    const top = Math.min(start.y, end.y);
    const width = Math.abs(end.x - start.x);
    const height = Math.abs(end.y - start.y);

    ctx.lineWidth = 2;
    ctx.strokeStyle = BORDER_COLOR;
    ctx.setLineDash([8, 4]);
    ctx.fillStyle = "rgba(108, 240, 138, 0.16)";
    ctx.fillRect(left, top, width, height);
    ctx.strokeRect(left, top, width, height);
    ctx.setLineDash([]);
}

function renderPreview(node) {
    const canvas = node.__loadImageCroppedPreviewCanvas;
    if (!canvas) {
        return;
    }

    const previewHeight = getAvailablePreviewHeight(node);
    const canvasHeight = Math.max(1, previewHeight - INFO_HEIGHT);
    const container = node.__loadImageCroppedPreviewContainer;
    if (container) {
        container.style.height = `${previewHeight}px`;
    }
    canvas.style.height = `${canvasHeight}px`;

    ensurePreviewImage(node);

    const ctx = canvas.getContext("2d");
    const cssWidth = Math.max(1, canvas.clientWidth || 1);
    const cssHeight = Math.max(1, canvas.clientHeight || 1);
    const dpr = window.devicePixelRatio || 1;

    if (canvas.width !== Math.round(cssWidth * dpr) || canvas.height !== Math.round(cssHeight * dpr)) {
        canvas.width = Math.round(cssWidth * dpr);
        canvas.height = Math.round(cssHeight * dpr);
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.clearRect(0, 0, cssWidth, cssHeight);
    ctx.fillStyle = "#111";
    ctx.fillRect(0, 0, cssWidth, cssHeight);

    const image = node.__loadImageCroppedImage;
    const info = node.__loadImageCroppedInfo;
    if (info) {
        if (image?.width && image?.height) {
            const crop = node.__loadImageCroppedDraftCrop ?? getStoredCrop(node);
            const normalizedCrop = normalizeCrop(crop, image.width, image.height);
            info.textContent = `${image.width} x ${image.height} | crop ${normalizedCrop.width} x ${normalizedCrop.height}`;
        } else {
            info.textContent = "";
        }
    }

    if (!image || !image.width || !image.height) {
        return;
    }

    const rect = getCanvasRect(node);
    node.__loadImageCroppedCanvasRect = rect;
    ctx.drawImage(image, rect.x, rect.y, rect.width, rect.height);

    const crop = node.__loadImageCroppedDraftCrop ?? getStoredCrop(node);
    drawCrop(ctx, rect, crop);
}

function seedPreviewMetrics(node) {
    if (node.__loadImageCroppedMetricsSeeded) {
        return;
    }
    node.__loadImageCroppedMetricsSeeded = true;
    node.__loadImageCroppedPreviewHeight = DEFAULT_PREVIEW_HEIGHT;
    node.__loadImageCroppedLastOuterHeight = node.size?.[1] ?? DEFAULT_PREVIEW_HEIGHT;
    node.__loadImageCroppedIgnoreResize = false;
}

function setupPreviewWidget(node) {
    if (node.__loadImageCroppedPreviewWidget) {
        return;
    }

    seedPreviewMetrics(node);

    const container = document.createElement("div");
    container.style.width = "100%";
    container.style.display = "flex";
    container.style.flexDirection = "column";
    container.style.background = "#111";
    container.style.overflow = "hidden";
    container.style.boxSizing = "border-box";

    const canvas = document.createElement("canvas");
    canvas.style.width = "100%";
    canvas.style.height = `${Math.max(1, getAvailablePreviewHeight(node) - INFO_HEIGHT)}px`;
    canvas.style.display = "block";
    canvas.style.background = "#111";
    canvas.style.imageRendering = "auto";
    canvas.style.cursor = "crosshair";
    canvas.style.touchAction = "none";
    canvas.style.pointerEvents = "auto";

    const info = document.createElement("div");
    info.style.height = `${INFO_HEIGHT}px`;
    info.style.lineHeight = `${INFO_HEIGHT}px`;
    info.style.padding = "0 8px";
    info.style.boxSizing = "border-box";
    info.style.color = "#b8b8b8";
    info.style.fontSize = "12px";
    info.style.fontFamily = "sans-serif";
    info.style.background = "#111";
    info.style.borderTop = "1px solid rgba(255, 255, 255, 0.06)";
    info.textContent = "";

    container.append(canvas, info);
    container.style.height = `${getAvailablePreviewHeight(node)}px`;

    node.__loadImageCroppedPreviewCanvas = canvas;
    node.__loadImageCroppedPreviewContainer = container;
    node.__loadImageCroppedInfo = info;
    node.__loadImageCroppedDraftCrop = null;
    node.__loadImageCroppedDragging = false;

    const widget = node.addDOMWidget("crop_preview", "crop_preview", container, {
        getValue() {
            return "";
        },
        setValue() {},
        serialize: false,
        hideOnZoom: false,
    });

    widget.computeSize = (width) => [width, MIN_PREVIEW_HEIGHT];
    widget.onRemove = () => container.remove();
    node.__loadImageCroppedPreviewWidget = widget;

    const startDrag = (event) => {
        const rect = node.__loadImageCroppedCanvasRect ?? getCanvasRect(node);
        if (!rect) {
            return;
        }

        const pos = getPointerPos(canvas, event);
        if (!isInsideRect(rect, pos)) {
            return;
        }

        const point = localToImage(rect, pos);
        node.__loadImageCroppedDragging = true;
        node.__loadImageCroppedDraftCrop = {
            x1: point.x,
            y1: point.y,
            x2: point.x,
            y2: point.y,
        };
        canvas.setPointerCapture?.(event.pointerId);
        event.preventDefault();
        event.stopPropagation();
        renderPreview(node);
    };

    const moveDrag = (event) => {
        if (!node.__loadImageCroppedDragging || !node.__loadImageCroppedDraftCrop) {
            return;
        }

        const rect = node.__loadImageCroppedCanvasRect ?? getCanvasRect(node);
        if (!rect) {
            return;
        }

        const pos = getPointerPos(canvas, event);
        const point = localToImage(rect, pos);
        node.__loadImageCroppedDraftCrop.x2 = point.x;
        node.__loadImageCroppedDraftCrop.y2 = point.y;
        event.preventDefault();
        event.stopPropagation();
        renderPreview(node);
    };

    const finishDrag = (event) => {
        if (!node.__loadImageCroppedDragging || !node.__loadImageCroppedDraftCrop) {
            return;
        }

        moveDrag(event);
        setStoredCrop(node, node.__loadImageCroppedDraftCrop);
        node.__loadImageCroppedDragging = false;
        node.__loadImageCroppedDraftCrop = null;
        canvas.releasePointerCapture?.(event.pointerId);
        event.preventDefault();
        event.stopPropagation();
        renderPreview(node);
    };

    const cancelDrag = () => {
        if (!node.__loadImageCroppedDragging) {
            return;
        }
        node.__loadImageCroppedDragging = false;
        node.__loadImageCroppedDraftCrop = null;
        renderPreview(node);
    };

    canvas.addEventListener("pointerdown", (event) => {
        if (event.button === 0) {
            startDrag(event);
        } else if (event.button === 1) {
            app.canvas.processMouseDown(event);
        }
    });

    canvas.addEventListener("pointermove", (event) => {
        if (node.__loadImageCroppedDragging) {
            moveDrag(event);
        } else if ((event.buttons & 4) === 4) {
            app.canvas.processMouseMove(event);
        }
    });

    canvas.addEventListener("pointerup", (event) => {
        if (event.button === 0) {
            finishDrag(event);
        } else if (event.button === 1) {
            app.canvas.processMouseUp(event);
        }
    });

    canvas.addEventListener("pointercancel", cancelDrag);
    canvas.addEventListener("lostpointercapture", cancelDrag);
    canvas.addEventListener("dragover", (event) => {
        if (!event.dataTransfer?.types?.includes?.("Files")) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        event.dataTransfer.dropEffect = "copy";
    });
    canvas.addEventListener("drop", async (event) => {
        if (!event.dataTransfer?.types?.includes?.("Files")) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        const file = event.dataTransfer.files?.[0];
        if (file) {
            await uploadImageFile(node, file);
        }
    });

    const observer = new ResizeObserver(() => renderPreview(node));
    observer.observe(canvas);
    widget.onRemove = () => {
        observer.disconnect();
        container.remove();
    };
}

function installNodeHandlers(node) {
    if (node.__loadImageCroppedHandlersInstalled) {
        return;
    }
    node.__loadImageCroppedHandlersInstalled = true;

    HIDDEN_WIDGETS.map((name) => getWidget(node, name)).forEach(hideWidget);
    setupPreviewWidget(node);

    const imageWidget = getWidget(node, "image");
    if (imageWidget) {
        const originalCallback = imageWidget.callback;
        imageWidget.callback = function () {
            node.__loadImageCroppedFilename = null;
            node.__loadImageCroppedImage = null;
            renderPreview(node);
            return originalCallback?.apply(this, arguments);
        };
    }

    node.onDragOver = function (event) {
        return !!event?.dataTransfer?.types?.includes?.("Files");
    };

    node.onDragDrop = async function (event) {
        if (!event?.dataTransfer?.types?.includes?.("Files")) {
            return false;
        }
        const file = event.dataTransfer.files?.[0];
        if (!file) {
            return false;
        }
        return await uploadImageFile(this, file);
    };

    const originalOnResize = node.onResize;
    node.onResize = function (size) {
        const result = originalOnResize?.apply(this, arguments);
        const outerHeight = size?.[1] ?? this.size?.[1] ?? 0;
        const lastOuterHeight = this.__loadImageCroppedLastOuterHeight;
        const canvas = this.__loadImageCroppedPreviewCanvas;
        const container = this.__loadImageCroppedPreviewContainer;

        if (this.__loadImageCroppedIgnoreResize) {
            this.__loadImageCroppedIgnoreResize = false;
            this.__loadImageCroppedLastOuterHeight = outerHeight;
            renderPreview(this);
            return result;
        }

        if (typeof lastOuterHeight === "number") {
            const delta = outerHeight - lastOuterHeight;
            if (delta !== 0) {
                this.__loadImageCroppedIgnoreResize = true;
                setPreviewHeight(this, getPreviewHeight(this) + delta);
            }
        }

        this.__loadImageCroppedLastOuterHeight = outerHeight;
        renderPreview(this);
        return result;
    };

    const originalGetExtraMenuOptions = node.getExtraMenuOptions;
    node.getExtraMenuOptions = function (_, options) {
        originalGetExtraMenuOptions?.apply(this, arguments);
        options.push({
            content: "Clear Crop",
            callback: () => {
                setStoredCrop(this, { x1: 0, y1: 0, x2: 0, y2: 0 });
                this.__loadImageCroppedDraftCrop = null;
                this.__loadImageCroppedDragging = false;
                renderPreview(this);
            },
        });
    };
}

app.registerExtension({
    name: "pepeutils.load_image_cropped",
    async nodeCreated(node) {
        if (node?.comfyClass !== NODE_CLASS) {
            return;
        }
        installNodeHandlers(node);
        renderPreview(node);
    },
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_CLASS) {
            return;
        }

        const originalOnDrawBackground = nodeType.prototype.onDrawBackground;
        nodeType.prototype.onDrawBackground = function (ctx) {
            const savedImgs = this.imgs;
            this.imgs = [];
            try {
                return originalOnDrawBackground?.apply(this, arguments);
            } finally {
                this.imgs = savedImgs;
            }
        };

        const originalOnRemoved = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            this.__loadImageCroppedPreviewContainer?.remove();
            return originalOnRemoved?.apply(this, arguments);
        };
    },
});
