import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "PasteImage";
const TEMP_SUBFOLDER = "pepeutils/paste-image";
const activeNodes = new Set();

function getImageWidget(node) {
    return node.widgets?.find((widget) => widget.name === "image") ?? null;
}

function hideWidget(widget) {
    if (!widget || widget.__pasteImageHidden) {
        return;
    }

    widget.__pasteImageHidden = true;
    widget.computeSize = () => [0, 0];
    widget.hidden = true;
}

function setStatus(node, message, isError = false) {
    if (!node.__pasteImageStatus) {
        return;
    }
    node.__pasteImageStatus.textContent = message;
    node.__pasteImageStatus.style.color = isError ? "#ff8a80" : "#b8b8c0";
}

function splitAnnotatedPath(value) {
    const path = String(value ?? "")
        .replace(/\s*\[temp\]\s*$/, "")
        .replaceAll("\\", "/");
    const separator = path.lastIndexOf("/");
    return {
        filename: separator >= 0 ? path.slice(separator + 1) : path,
        subfolder: separator >= 0 ? path.slice(0, separator) : "",
    };
}

function makeViewUrl(value) {
    const { filename, subfolder } = splitAnnotatedPath(value);
    if (!filename) {
        return null;
    }

    const params = new URLSearchParams({ filename, type: "temp" });
    if (subfolder) {
        params.set("subfolder", subfolder);
    }
    return api.apiURL(`/view?${params.toString()}`);
}

function refreshPreview(node) {
    const value = getImageWidget(node)?.value;
    const url = makeViewUrl(value);
    const image = node.__pasteImagePreview;
    if (!image) {
        return;
    }

    if (!url) {
        image.removeAttribute("src");
        image.style.display = "none";
        setStatus(node, "Select this node, then press Ctrl+V.");
        return;
    }

    image.onload = () => {
        image.style.display = "block";
        setStatus(node, `${image.naturalWidth} × ${image.naturalHeight} · temporary`);
        node.setDirtyCanvas(true, true);
    };
    image.onerror = () => {
        image.style.display = "none";
        setStatus(node, "Temporary image is no longer available. Paste it again.", true);
    };
    image.src = `${url}&t=${Date.now()}`;
}

function extensionForMimeType(mimeType) {
    return {
        "image/bmp": "bmp",
        "image/gif": "gif",
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
    }[mimeType] ?? "png";
}

async function uploadClipboardImage(node, blob) {
    if (!blob?.type?.startsWith("image/")) {
        setStatus(node, "The clipboard does not contain an image.", true);
        return false;
    }

    setStatus(node, "Uploading clipboard image…");
    const extension = extensionForMimeType(blob.type);
    const uniqueId = globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
    const filename = `clipboard-${Date.now()}-${uniqueId}.${extension}`;
    const file = new File([blob], filename, { type: blob.type });
    const body = new FormData();
    body.append("image", file, filename);
    body.append("type", "temp");
    body.append("subfolder", TEMP_SUBFOLDER);

    try {
        const response = await api.fetchApi("/upload/image", {
            method: "POST",
            body,
        });
        if (!response.ok) {
            throw new Error(`Upload failed with HTTP ${response.status}`);
        }

        const data = await response.json();
        const subfolder = String(data.subfolder ?? TEMP_SUBFOLDER).replaceAll("\\", "/").replace(/^\/+|\/+$/g, "");
        const value = `${subfolder ? `${subfolder}/` : ""}${data.name} [temp]`;
        const widget = getImageWidget(node);
        if (!widget) {
            throw new Error("The image storage widget is unavailable.");
        }

        widget.value = value;
        widget.callback?.(value);
        refreshPreview(node);
        node.setDirtyCanvas(true, true);
        app.graph?.setDirtyCanvas?.(true, true);
        return true;
    } catch (error) {
        console.error("[PepeUtils Paste Image]", error);
        setStatus(node, `Could not paste image: ${error.message}`, true);
        return false;
    }
}

async function readClipboardForNode(node) {
    if (!navigator.clipboard?.read) {
        setStatus(node, "Clipboard button unavailable here. Select the node and press Ctrl+V.", true);
        return;
    }

    try {
        const items = await navigator.clipboard.read();
        for (const item of items) {
            const imageType = item.types.find((type) => type.startsWith("image/"));
            if (imageType) {
                await uploadClipboardImage(node, await item.getType(imageType));
                return;
            }
        }
        setStatus(node, "The clipboard does not contain an image.", true);
    } catch (error) {
        console.error("[PepeUtils Paste Image]", error);
        setStatus(node, "Clipboard access was denied. Select the node and press Ctrl+V.", true);
    }
}

function setupPreview(node) {
    const container = document.createElement("div");
    container.style.cssText = [
        "width: 100%",
        "height: 230px",
        "box-sizing: border-box",
        "display: flex",
        "flex-direction: column",
        "align-items: center",
        "justify-content: center",
        "gap: 6px",
        "padding: 8px",
        "overflow: hidden",
        "background: #18181c",
        "border: 1px dashed #555",
        "border-radius: 6px",
        "pointer-events: none",
    ].join(";");

    const image = document.createElement("img");
    image.alt = "Clipboard image preview";
    image.style.cssText = "display:none;max-width:100%;min-height:0;flex:1;object-fit:contain;";

    const status = document.createElement("div");
    status.style.cssText = "width:100%;min-height:18px;text-align:center;font-size:11px;color:#b8b8c0;";

    container.append(image, status);
    const widget = node.addDOMWidget("clipboard_preview", "clipboard_preview", container, {
        serialize: false,
        hideOnZoom: false,
    });
    widget.computeSize = (width) => [width, 230];

    node.__pasteImagePreview = image;
    node.__pasteImageStatus = status;
    refreshPreview(node);
}

function installNode(node) {
    hideWidget(getImageWidget(node));
    node.addWidget("button", "Paste image from clipboard", null, () => readClipboardForNode(node));
    setupPreview(node);
    node.setSize([Math.max(node.size?.[0] ?? 0, 280), Math.max(node.size?.[1] ?? 0, 310)]);
    activeNodes.add(node);
}

document.addEventListener("paste", (event) => {
    const selectedNodes = [...activeNodes].filter((node) => app.canvas?.selected_nodes?.[node.id]);
    if (selectedNodes.length !== 1) {
        return;
    }

    const imageItem = [...(event.clipboardData?.items ?? [])]
        .find((item) => item.kind === "file" && item.type.startsWith("image/"));
    const file = imageItem?.getAsFile();
    if (!file) {
        return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();
    uploadClipboardImage(selectedNodes[0], file);
}, { capture: true });

app.registerExtension({
    name: "pepeutils.paste_image",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_CLASS) {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);
            installNode(this);
            return result;
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = onConfigure?.apply(this, arguments);
            setTimeout(() => refreshPreview(this), 0);
            return result;
        };

        const onRemoved = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            activeNodes.delete(this);
            this.__pasteImagePreview?.remove();
            return onRemoved?.apply(this, arguments);
        };
    },
});
