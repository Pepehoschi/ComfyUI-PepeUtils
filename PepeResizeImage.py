import math

import torch
import torch.nn.functional as F

from comfy.utils import common_upscale

from .PepeScaleImageBy import scale_photoshop_bicubic_sharper


KEEP_PROPORTION_MODES = [
    "stretch",
    "resize",
    "pad",
    "pad_edge",
    "pad_edge_pixel",
    "crop",
    "pillarbox_blur",
    "total_pixels",
]
CROP_POSITIONS = ["center", "top", "bottom", "left", "right"]


def align_down(value, stride):
    stride = max(int(stride), 1)
    value = max(int(round(value)), 1)
    return max(stride, (value // stride) * stride)


def resolve_requested_dimensions(requested_w, requested_h, source_w, source_h):
    requested_w = int(requested_w)
    requested_h = int(requested_h)

    if requested_w == 0 and requested_h == 0:
        return source_w, source_h
    if requested_w == 0:
        return max(1, round(source_w * (requested_h / source_h))), max(1, requested_h)
    if requested_h == 0:
        return max(1, requested_w), max(1, round(source_h * (requested_w / source_w)))
    return max(1, requested_w), max(1, requested_h)


def fit_dimensions(source_w, source_h, bound_w, bound_h, stride, cover=False):
    scale = max(bound_w / source_w, bound_h / source_h) if cover else min(bound_w / source_w, bound_h / source_h)
    width = align_down(source_w * scale, stride)
    height = align_down(source_h * scale, stride)

    if cover:
        while width < bound_w:
            width += stride
        while height < bound_h:
            height += stride
    else:
        width = min(width, bound_w)
        height = min(height, bound_h)

    return max(stride, width), max(stride, height)


def total_pixel_dimensions(source_w, source_h, requested_w, requested_h, stride):
    target_pixels = max(int(requested_w) * int(requested_h), 1)
    aspect = source_w / source_h
    width = align_down(math.sqrt(target_pixels * aspect), stride)
    height = align_down(math.sqrt(target_pixels / aspect), stride)
    return width, height


def placement_offsets(canvas_w, canvas_h, content_w, content_h, crop_position):
    if crop_position == "top":
        return (canvas_w - content_w) // 2, 0
    if crop_position == "bottom":
        return (canvas_w - content_w) // 2, canvas_h - content_h
    if crop_position == "left":
        return 0, (canvas_h - content_h) // 2
    if crop_position == "right":
        return canvas_w - content_w, (canvas_h - content_h) // 2
    return (canvas_w - content_w) // 2, (canvas_h - content_h) // 2


def crop_offsets(content_w, content_h, canvas_w, canvas_h, crop_position):
    excess_w = max(content_w - canvas_w, 0)
    excess_h = max(content_h - canvas_h, 0)
    if crop_position == "top":
        return excess_w // 2, 0
    if crop_position == "bottom":
        return excess_w // 2, excess_h
    if crop_position == "left":
        return 0, excess_h // 2
    if crop_position == "right":
        return excess_w, excess_h // 2
    return excess_w // 2, excess_h // 2


def calculate_geometry(source_w, source_h, requested_w, requested_h, keep_proportion, divisible_by):
    stride = max(int(divisible_by), 1)
    requested_w, requested_h = resolve_requested_dimensions(requested_w, requested_h, source_w, source_h)

    if keep_proportion == "total_pixels":
        resize_w, resize_h = total_pixel_dimensions(source_w, source_h, requested_w, requested_h, stride)
        return {
            "canvas_w": resize_w,
            "canvas_h": resize_h,
            "resize_w": resize_w,
            "resize_h": resize_h,
        }

    canvas_w = align_down(requested_w, stride)
    canvas_h = align_down(requested_h, stride)

    if keep_proportion == "stretch":
        resize_w, resize_h = canvas_w, canvas_h
    elif keep_proportion == "resize":
        resize_w, resize_h = fit_dimensions(source_w, source_h, canvas_w, canvas_h, stride, cover=False)
        canvas_w, canvas_h = resize_w, resize_h
    elif keep_proportion == "crop":
        resize_w, resize_h = fit_dimensions(source_w, source_h, canvas_w, canvas_h, stride, cover=True)
    else:
        resize_w, resize_h = fit_dimensions(source_w, source_h, canvas_w, canvas_h, stride, cover=False)

    return {
        "canvas_w": canvas_w,
        "canvas_h": canvas_h,
        "resize_w": resize_w,
        "resize_h": resize_h,
    }


def _resize_lanczos(image, width, height):
    if image.shape[1] == height and image.shape[2] == width:
        return image
    return common_upscale(image.movedim(-1, 1), width, height, "lanczos", crop="disabled").movedim(1, -1)


def resize_photoshop_bicubic_sharper(image, width, height, clamp_intermediate=True):
    if image.shape[1] == height and image.shape[2] == width:
        return image

    source = image.detach().cpu().numpy()
    output = torch.empty((image.shape[0], height, width, image.shape[3]), dtype=torch.float32)
    for index in range(image.shape[0]):
        output[index] = torch.from_numpy(
            scale_photoshop_bicubic_sharper(source[index], width, height, clamp_intermediate)
        )
    return output.to(device=image.device, dtype=image.dtype)


def resize_image_auto(image, width, height):
    current_h, current_w = image.shape[1], image.shape[2]
    if current_w == width and current_h == height:
        return image

    shrink_w = width < current_w
    shrink_h = height < current_h
    grow_w = width > current_w
    grow_h = height > current_h

    if shrink_w and not shrink_h:
        image = resize_photoshop_bicubic_sharper(image, width, current_h)
        current_w = width
    if shrink_h and not shrink_w:
        image = resize_photoshop_bicubic_sharper(image, current_w, height)
        current_h = height

    if width <= current_w and height <= current_h:
        return resize_photoshop_bicubic_sharper(image, width, height)
    if width >= current_w and height >= current_h:
        return _resize_lanczos(image, width, height)

    if shrink_w:
        image = resize_photoshop_bicubic_sharper(image, width, current_h)
    if shrink_h:
        image = resize_photoshop_bicubic_sharper(image, image.shape[2], height)
    if image.shape[2] != width or image.shape[1] != height:
        image = _resize_lanczos(image, width, height)
    return image


def normalize_mask(mask, batch, height, width, device):
    if mask is None:
        return torch.zeros((batch, height, width), dtype=torch.float32, device=device)

    if mask.ndim == 2:
        mask = mask.unsqueeze(0)
    mask = mask.to(device=device, dtype=torch.float32)
    if mask.shape[0] == 1 and batch > 1:
        mask = mask.repeat(batch, 1, 1)
    elif mask.shape[0] != batch:
        raise ValueError(f"Mask batch {mask.shape[0]} does not match image batch {batch}")
    if mask.shape[-2:] != (height, width):
        mask = resize_mask(mask, width, height)
    return mask.clamp(0.0, 1.0)


def resize_mask(mask, width, height):
    if mask.shape[-2:] == (height, width):
        return mask
    return F.interpolate(mask.unsqueeze(1), size=(height, width), mode="bilinear", align_corners=False).squeeze(1).clamp(0.0, 1.0)


def make_color_canvas(image, width, height, color):
    rgb = torch.tensor([channel / 255.0 for channel in color], dtype=image.dtype, device=image.device)
    return rgb.view(1, 1, 1, 3).repeat(image.shape[0], height, width, 1)


def paste_image(canvas, content, x, y):
    canvas[:, y : y + content.shape[1], x : x + content.shape[2], :] = content
    return canvas


def paste_mask(canvas, content, x, y):
    canvas[:, y : y + content.shape[1], x : x + content.shape[2]] = content
    return canvas


def pad_edge_average(content, canvas_w, canvas_h, x, y, fallback):
    canvas = fallback.clone()
    batch, content_h, content_w, channels = content.shape
    canvas = paste_image(canvas, content, x, y)

    left = content[:, :, 0:1, :].mean(dim=1, keepdim=True)
    right = content[:, :, -1:, :].mean(dim=1, keepdim=True)
    top = content[:, 0:1, :, :].mean(dim=2, keepdim=True)
    bottom = content[:, -1:, :, :].mean(dim=2, keepdim=True)

    if x > 0:
        canvas[:, y : y + content_h, :x, :] = left
    if x + content_w < canvas_w:
        canvas[:, y : y + content_h, x + content_w :, :] = right
    if y > 0:
        canvas[:, :y, :, :] = top.expand(batch, y, canvas_w, channels)
    if y + content_h < canvas_h:
        canvas[:, y + content_h :, :, :] = bottom.expand(batch, canvas_h - y - content_h, canvas_w, channels)

    return paste_image(canvas, content, x, y)


def pad_edge_pixel(content, canvas_w, canvas_h, x, y):
    pad_left = x
    pad_right = canvas_w - x - content.shape[2]
    pad_top = y
    pad_bottom = canvas_h - y - content.shape[1]
    nchw = content.movedim(-1, 1)
    padded = F.pad(nchw, (pad_left, pad_right, pad_top, pad_bottom), mode="replicate")
    return padded.movedim(1, -1)


def crop_tensor(content, canvas_w, canvas_h, crop_position):
    x, y = crop_offsets(content.shape[2], content.shape[1], canvas_w, canvas_h, crop_position)
    return content[:, y : y + canvas_h, x : x + canvas_w, :]


def crop_mask(content, canvas_w, canvas_h, crop_position):
    x, y = crop_offsets(content.shape[2], content.shape[1], canvas_w, canvas_h, crop_position)
    return content[:, y : y + canvas_h, x : x + canvas_w]


def _blur_image(image, radius):
    radius = max(int(radius), 1)
    kernel = radius * 2 + 1
    nchw = image.movedim(-1, 1)
    blurred = F.avg_pool2d(nchw, kernel_size=kernel, stride=1, padding=radius)
    return blurred.movedim(1, -1)


class PepeResizeImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "width": ("INT", {"default": 1024, "min": 0, "step": 1}),
                "height": ("INT", {"default": 1024, "min": 0, "step": 1}),
                "keep_proportion": (KEEP_PROPORTION_MODES, {"default": "resize"}),
                "pad_color_r": ("INT", {"default": 0, "min": 0, "max": 255}),
                "pad_color_g": ("INT", {"default": 0, "min": 0, "max": 255}),
                "pad_color_b": ("INT", {"default": 0, "min": 0, "max": 255}),
                "crop_position": (CROP_POSITIONS, {"default": "center"}),
                "divisible_by": ("INT", {"default": 8, "min": 1, "step": 1}),
            },
            "optional": {
                "mask": ("MASK",),
            },
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT", "MASK")
    RETURN_NAMES = ("image", "width", "height", "mask")
    FUNCTION = "resize"
    CATEGORY = "utils/image"

    def resize(
        self,
        image,
        width,
        height,
        keep_proportion,
        pad_color_r,
        pad_color_g,
        pad_color_b,
        crop_position,
        divisible_by,
        mask=None,
    ):
        if image.ndim != 4:
            raise ValueError("image must be a BHWC tensor")

        batch, source_h, source_w, _channels = image.shape
        geometry = calculate_geometry(source_w, source_h, width, height, keep_proportion, divisible_by)
        canvas_w = geometry["canvas_w"]
        canvas_h = geometry["canvas_h"]
        resize_w = geometry["resize_w"]
        resize_h = geometry["resize_h"]
        pad_color = (int(pad_color_r), int(pad_color_g), int(pad_color_b))

        work_mask = normalize_mask(mask, batch, source_h, source_w, image.device)

        if keep_proportion == "stretch":
            out_image = resize_image_auto(image, canvas_w, canvas_h)
            out_mask = resize_mask(work_mask, canvas_w, canvas_h)
        elif keep_proportion in ("resize", "total_pixels"):
            out_image = resize_image_auto(image, resize_w, resize_h)
            out_mask = resize_mask(work_mask, resize_w, resize_h)
        elif keep_proportion == "crop":
            resized = resize_image_auto(image, resize_w, resize_h)
            resized_mask = resize_mask(work_mask, resize_w, resize_h)
            out_image = crop_tensor(resized, canvas_w, canvas_h, crop_position)
            out_mask = crop_mask(resized_mask, canvas_w, canvas_h, crop_position)
        elif keep_proportion == "pillarbox_blur":
            foreground = resize_image_auto(image, resize_w, resize_h)
            foreground_mask = resize_mask(work_mask, resize_w, resize_h)
            bg_w, bg_h = fit_dimensions(source_w, source_h, canvas_w, canvas_h, max(int(divisible_by), 1), cover=True)
            background = _resize_lanczos(image, bg_w, bg_h)
            background = crop_tensor(background, canvas_w, canvas_h, "center")
            background = _blur_image(background, max(canvas_w, canvas_h) // 50)
            x, y = placement_offsets(canvas_w, canvas_h, resize_w, resize_h, crop_position)
            out_image = paste_image(background, foreground, x, y)
            out_mask = paste_mask(torch.zeros((batch, canvas_h, canvas_w), dtype=work_mask.dtype, device=work_mask.device), foreground_mask, x, y)
        else:
            resized = resize_image_auto(image, resize_w, resize_h)
            resized_mask = resize_mask(work_mask, resize_w, resize_h)
            x, y = placement_offsets(canvas_w, canvas_h, resize_w, resize_h, crop_position)
            if keep_proportion == "pad_edge_pixel":
                out_image = pad_edge_pixel(resized, canvas_w, canvas_h, x, y)
            elif keep_proportion == "pad_edge":
                fallback = make_color_canvas(image, canvas_w, canvas_h, pad_color)
                out_image = pad_edge_average(resized, canvas_w, canvas_h, x, y, fallback)
            else:
                out_image = paste_image(make_color_canvas(image, canvas_w, canvas_h, pad_color), resized, x, y)
            out_mask = paste_mask(torch.zeros((batch, canvas_h, canvas_w), dtype=work_mask.dtype, device=work_mask.device), resized_mask, x, y)

        out_image = out_image.clamp(0.0, 1.0)
        out_mask = out_mask.clamp(0.0, 1.0)
        if out_image.shape[1] != out_mask.shape[1] or out_image.shape[2] != out_mask.shape[2]:
            raise RuntimeError("image and mask output dimensions do not match")

        return (out_image, out_image.shape[2], out_image.shape[1], out_mask)


NODE_CLASS_MAPPINGS = {
    "PepeResizeImage": PepeResizeImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PepeResizeImage": "Pepe Resize Image",
}
