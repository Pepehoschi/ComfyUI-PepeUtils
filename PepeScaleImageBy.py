import math

import numpy as np
import torch


def _cubic_bc(x, b, c):
    x = np.abs(x)
    x2 = x * x
    x3 = x2 * x

    y = np.zeros_like(x, dtype=np.float32)
    near = x < 1.0
    far = (x >= 1.0) & (x < 2.0)

    y[near] = (
        (12.0 - 9.0 * b - 6.0 * c) * x3[near]
        + (-18.0 + 12.0 * b + 6.0 * c) * x2[near]
        + (6.0 - 2.0 * b)
    ) / 6.0
    y[far] = (
        (-b - 6.0 * c) * x3[far]
        + (6.0 * b + 30.0 * c) * x2[far]
        + (-12.0 * b - 48.0 * c) * x[far]
        + (8.0 * b + 24.0 * c)
    ) / 6.0

    return y


def _coordinate_center(out_pos, scale, coordinate_mode):
    if coordinate_mode == "integer_center":
        return out_pos / scale
    return (out_pos + 0.5) / scale - 0.5


def _cubic_weights(
    src_size,
    dst_size,
    b,
    c,
    blur,
    antialias,
    antialias_strength,
    filter_scale_override,
    coordinate_mode,
    center_scale,
):
    scale = dst_size / src_size
    if antialias and filter_scale_override > 0.0:
        filter_scale = min(max(float(filter_scale_override), 0.01), 1.0)
    elif antialias:
        strength = min(max(float(antialias_strength), 0.0), 1.0)
        filter_scale = 1.0 - (1.0 - min(1.0, scale)) * strength
    else:
        filter_scale = 1.0
    support = 2.0 * blur / filter_scale
    taps = int(math.ceil(support) * 2 + 1)
    indices = np.empty((dst_size, taps), dtype=np.int64)
    weights = np.empty((dst_size, taps), dtype=np.float32)

    for out_pos in range(dst_size):
        center = _coordinate_center(out_pos, scale, coordinate_mode)
        if center_scale != 1.0:
            src_mid = (src_size - 1.0) * 0.5
            center = src_mid + (center - src_mid) * center_scale
        start = math.floor(center - support)
        src_positions = start + np.arange(taps, dtype=np.float32)
        raw_weights = _cubic_bc((src_positions - center) * filter_scale / blur, b, c)
        weight_sum = float(raw_weights.sum())
        if weight_sum != 0.0:
            raw_weights /= weight_sum

        indices[out_pos] = np.clip(start + np.arange(taps), 0, src_size - 1)
        weights[out_pos] = raw_weights

    return indices, weights


def _map_center(out_pos, scale, phase, phase_mode, phase_units, coordinate_mode):
    base = _coordinate_center(out_pos, scale, coordinate_mode)
    if phase_units == "source":
        if phase_mode == "legacy_offset":
            return base + phase
        return base - phase

    if phase_mode == "legacy_offset":
        return _coordinate_center(out_pos + phase, scale, coordinate_mode)
    return _coordinate_center(out_pos - phase, scale, coordinate_mode)


def _box_weights_area(src_size, dst_size, phase, phase_mode, phase_units, coordinate_mode):
    scale = dst_size / src_size
    max_taps = int(math.ceil(1.0 / scale)) + 2 if scale < 1.0 else 2
    indices = np.zeros((dst_size, max_taps), dtype=np.int64)
    weights = np.zeros((dst_size, max_taps), dtype=np.float32)

    for out_pos in range(dst_size):
        center = _map_center(out_pos, scale, phase, phase_mode, phase_units, coordinate_mode)
        width = 1.0 / scale
        left = center - width * 0.5
        right = center + width * 0.5
        first = int(math.floor(left))
        last = int(math.ceil(right))
        tap = 0

        for src_pos in range(first, last):
            overlap = min(right, src_pos + 1.0) - max(left, src_pos)
            if overlap <= 0.0:
                continue
            indices[out_pos, tap] = min(max(src_pos, 0), src_size - 1)
            weights[out_pos, tap] = overlap
            tap += 1

        weight_sum = float(weights[out_pos].sum())
        if weight_sum != 0.0:
            weights[out_pos] /= weight_sum

    return indices, weights


def _box_weights_sampled(src_size, dst_size, phase, blur, phase_mode, phase_units, coordinate_mode):
    scale = dst_size / src_size
    filter_scale = min(1.0, scale)
    support = 0.5 * blur / filter_scale
    taps = int(math.ceil(support) * 2 + 1)
    indices = np.empty((dst_size, taps), dtype=np.int64)
    weights = np.empty((dst_size, taps), dtype=np.float32)

    for out_pos in range(dst_size):
        center = _map_center(out_pos, scale, phase, phase_mode, phase_units, coordinate_mode)
        start = math.floor(center - support)
        src_positions = start + np.arange(taps, dtype=np.float32)
        raw_weights = (np.abs((src_positions - center) * filter_scale / blur) <= 0.5).astype(np.float32)
        weight_sum = float(raw_weights.sum())
        if weight_sum != 0.0:
            raw_weights /= weight_sum

        indices[out_pos] = np.clip(start + np.arange(taps), 0, src_size - 1)
        weights[out_pos] = raw_weights

    return indices, weights


def _box_weights_integrated(src_size, dst_size, phase, blur, phase_mode, phase_units, coordinate_mode):
    scale = dst_size / src_size
    filter_scale = min(1.0, scale)
    support = 0.5 * blur / filter_scale
    taps = int(math.ceil(support + 0.5) * 2 + 1)
    indices = np.empty((dst_size, taps), dtype=np.int64)
    weights = np.zeros((dst_size, taps), dtype=np.float32)

    for out_pos in range(dst_size):
        center = _map_center(out_pos, scale, phase, phase_mode, phase_units, coordinate_mode)
        left = center - support
        right = center + support
        start = math.floor(left - 0.5)
        src_positions = start + np.arange(taps)

        for tap, src_pos in enumerate(src_positions):
            pixel_left = src_pos - 0.5
            pixel_right = src_pos + 0.5
            weights[out_pos, tap] = max(0.0, min(right, pixel_right) - max(left, pixel_left))

        weight_sum = float(weights[out_pos].sum())
        if weight_sum != 0.0:
            weights[out_pos] /= weight_sum

        indices[out_pos] = np.clip(src_positions, 0, src_size - 1)

    return indices, weights


def _box_weights_hybrid(src_size, dst_size, phase, blur, phase_mode, phase_units, coordinate_mode):
    scale = dst_size / src_size
    support = 0.5 * blur / min(1.0, scale)
    indices = np.empty((dst_size, 2), dtype=np.int64)
    weights = np.empty((dst_size, 2), dtype=np.float32)

    for out_pos in range(dst_size):
        center = _map_center(out_pos, scale, phase, phase_mode, phase_units, coordinate_mode)
        left_index = math.floor(center)
        fraction = center - left_index

        left_weight = (1.0 - fraction) * support
        right_weight = fraction * support
        weight_sum = left_weight + right_weight
        if weight_sum == 0.0:
            left_weight = 1.0
            right_weight = 0.0
        else:
            left_weight /= weight_sum
            right_weight /= weight_sum

        indices[out_pos, 0] = min(max(left_index, 0), src_size - 1)
        indices[out_pos, 1] = min(max(left_index + 1, 0), src_size - 1)
        weights[out_pos, 0] = left_weight
        weights[out_pos, 1] = right_weight

    return indices, weights


def _resample_axis(
    image,
    axis,
    dst_size,
    filter_kind,
    b=0.0,
    c=0.0,
    blur=1.0,
    phase=0.0,
    antialias=True,
    box_mode="sampled",
    phase_mode="translate",
    phase_units="source",
    coordinate_mode="half_pixel",
    antialias_strength=1.0,
    filter_scale_override=-1.0,
    center_scale=1.0,
):
    src_size = image.shape[axis]
    if src_size == dst_size:
        return image

    if filter_kind == "box":
        if box_mode == "area":
            indices, weights = _box_weights_area(src_size, dst_size, phase, phase_mode, phase_units, coordinate_mode)
        elif box_mode == "sampled":
            indices, weights = _box_weights_sampled(src_size, dst_size, phase, blur, phase_mode, phase_units, coordinate_mode)
        elif box_mode == "hybrid":
            indices, weights = _box_weights_hybrid(src_size, dst_size, phase, blur, phase_mode, phase_units, coordinate_mode)
        else:
            indices, weights = _box_weights_integrated(src_size, dst_size, phase, blur, phase_mode, phase_units, coordinate_mode)
    else:
        indices, weights = _cubic_weights(
            src_size,
            dst_size,
            b,
            c,
            blur,
            antialias,
            antialias_strength,
            filter_scale_override,
            coordinate_mode,
            center_scale,
        )

    moved = np.moveaxis(image, axis, 0)
    output_shape = (dst_size,) + moved.shape[1:]
    output = np.empty(output_shape, dtype=np.float32)

    for out_pos in range(dst_size):
        samples = moved[indices[out_pos]]
        output[out_pos] = np.tensordot(weights[out_pos], samples, axes=(0, 0))

    return np.moveaxis(output, 0, axis)


def _snap_size(value, stride, mode):
    if stride <= 1:
        return max(1, int(round(value)))

    if mode == "up":
        return max(stride, int(math.ceil((value - 1e-6) / stride) * stride))
    if mode == "down":
        return max(stride, int(math.floor((value + 1e-6) / stride) * stride))
    return max(stride, int(round(value / stride) * stride))


def _apply_intermediate_precision(image, precision, clamp):
    if precision == "uint8":
        return np.round(np.clip(image, 0.0, 1.0) * 255.0) / 255.0
    if precision == "uint16":
        return np.round(np.clip(image, 0.0, 1.0) * 65535.0) / 65535.0
    if clamp:
        return np.clip(image, 0.0, 1.0)
    return image


def _photoshop_sharper_c(scale):
    if scale > 1.0:
        return 1.0
    if scale >= 0.25:
        return 2.6 - 1.6 * scale
    return 2.2


def _effective_cubic_c(scale, cubic_c_override):
    if cubic_c_override >= 0.0:
        return cubic_c_override
    return _photoshop_sharper_c(scale)


def _scale_one(
    image,
    target_width,
    target_height,
    clamp_intermediate,
    box_phase_x,
    box_phase_y,
    box_blur,
    box_mode,
    box_phase_mode,
    box_phase_units,
    coordinate_mode,
    intermediate_precision,
    cubic_blur,
    cubic_c_override,
    cubic_antialias_strength,
    cubic_filter_scale_override,
    cubic_center_scale,
    cubic_antialias,
):
    src_height, src_width = image.shape[:2]
    out = image.astype(np.float32, copy=False)

    x_scale = target_width / src_width
    y_scale = target_height / src_height

    if target_width != src_width:
        if x_scale < 0.25:
            pre_width = max(target_width, target_width * 4)
            out = _resample_axis(
                out,
                1,
                pre_width,
                "box",
                blur=box_blur,
                phase=box_phase_x,
                box_mode=box_mode,
                phase_mode=box_phase_mode,
                phase_units=box_phase_units,
                coordinate_mode=coordinate_mode,
            )
            out = _apply_intermediate_precision(out, intermediate_precision, False)
        out = _resample_axis(
            out,
            1,
            target_width,
            "cubic",
            b=0.0,
            c=_effective_cubic_c(x_scale, cubic_c_override),
            blur=cubic_blur,
            antialias=cubic_antialias,
            antialias_strength=cubic_antialias_strength,
            filter_scale_override=cubic_filter_scale_override,
            coordinate_mode=coordinate_mode,
            center_scale=cubic_center_scale,
        )
        out = _apply_intermediate_precision(out, intermediate_precision, clamp_intermediate)

    if target_height != src_height:
        if y_scale < 0.25:
            pre_height = max(target_height, target_height * 4)
            out = _resample_axis(
                out,
                0,
                pre_height,
                "box",
                blur=box_blur,
                phase=box_phase_y,
                box_mode=box_mode,
                phase_mode=box_phase_mode,
                phase_units=box_phase_units,
                coordinate_mode=coordinate_mode,
            )
            out = _apply_intermediate_precision(out, intermediate_precision, False)
        out = _resample_axis(
            out,
            0,
            target_height,
            "cubic",
            b=0.0,
            c=_effective_cubic_c(y_scale, cubic_c_override),
            blur=cubic_blur,
            antialias=cubic_antialias,
            antialias_strength=cubic_antialias_strength,
            filter_scale_override=cubic_filter_scale_override,
            coordinate_mode=coordinate_mode,
            center_scale=cubic_center_scale,
        )
        out = _apply_intermediate_precision(out, intermediate_precision, clamp_intermediate)

    return np.clip(out, 0.0, 1.0)


def scale_photoshop_bicubic_sharper(image, target_width, target_height, clamp_intermediate=True):
    return _scale_one(
        image,
        target_width,
        target_height,
        bool(clamp_intermediate),
        0.3999,
        0.3999,
        0.33,
        "integrated",
        "translate",
        "source",
        "half_pixel",
        "none",
        1.05,
        -1.0,
        1.0,
        -1.0,
        1.0,
        True,
    )


class PepeScaleImageBy:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "scale_by": ("FLOAT", {"default": 0.5, "min": 0.01, "max": 16.0, "step": 0.01}),
                "snap_to_stride": ("BOOLEAN", {"default": False}),
                "stride": ("INT", {"default": 8, "min": 1, "max": 1024}),
                "snap_mode": (["nearest", "down", "up"], {"default": "nearest"}),
                "clamp_intermediate": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("IMAGE", "INT", "INT")
    RETURN_NAMES = ("image", "width", "height")
    FUNCTION = "scale"
    CATEGORY = "utils/image"

    def scale(
        self,
        image,
        scale_by,
        snap_to_stride,
        stride,
        snap_mode,
        clamp_intermediate,
    ):
        scale = max(float(scale_by), 0.01)
        batch, height, width, channels = image.shape

        target_width = max(1, int(round(width * scale)))
        target_height = max(1, int(round(height * scale)))
        if bool(snap_to_stride):
            target_width = _snap_size(target_width, int(stride), snap_mode)
            target_height = _snap_size(target_height, int(stride), snap_mode)

        if target_width == width and target_height == height:
            return (image, width, height)

        source = image.detach().cpu().numpy().astype(np.float32, copy=False)
        output = np.empty((batch, target_height, target_width, channels), dtype=np.float32)

        for index in range(batch):
            output[index] = scale_photoshop_bicubic_sharper(
                source[index], target_width, target_height, clamp_intermediate
            )

        return (torch.from_numpy(output), target_width, target_height)


NODE_CLASS_MAPPINGS = {
    "PepeScaleImageBy": PepeScaleImageBy,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PepeScaleImageBy": "Pepe Scale Image By",
}
