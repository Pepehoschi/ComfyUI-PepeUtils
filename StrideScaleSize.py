import math

class StrideScaleSize:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_width": ("INT", {"default": 1024, "min": 1}),
                "image_height": ("INT", {"default": 1024, "min": 1}),
                "rescale_by": ("FLOAT", {"default": 1.0, "min": 1.0}),  # upscale only
                "stride": ("INT", {"default": 8, "min": 1}),
                "mode": (["down", "up", "nearest"], {"default": "down"}),
                "side_selector": (["shortest", "longest"], {"default": "longest"}),
                "clamp_rescale_min_1": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = ("INT", "INT", "INT")
    RETURN_NAMES = (
        "scaled_width",
        "scaled_height",
        "chosen_side",
    )
    FUNCTION = "compute"
    CATEGORY = "utils/math"

    def compute(
        self,
        image_width,
        image_height,
        rescale_by,
        stride,
        mode="down",
        side_selector="longest",
        clamp_rescale_min_1=True,
    ):
        s = max(int(stride), 1)
        scale = max(float(rescale_by), 1.0) if clamp_rescale_min_1 else float(rescale_by)

        def snap(x):
            if mode == "up":
                return int(math.ceil((x - 1e-6) / s) * s)
            elif mode == "nearest":
                return int(round(x / s) * s)
            else:  # down
                return int(math.floor((x + 1e-6) / s) * s)

        scaled_w = max(1, snap(image_width * scale))
        scaled_h = max(1, snap(image_height * scale))

        shortest_side = min(scaled_w, scaled_h)
        longest_side = max(scaled_w, scaled_h)

        chosen_side = shortest_side if side_selector == "shortest" else longest_side

        return (scaled_w, scaled_h, chosen_side)


NODE_CLASS_MAPPINGS = {
    "StrideScaleSize": StrideScaleSize,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "StrideScaleSize": "Stride Scale Size",
}