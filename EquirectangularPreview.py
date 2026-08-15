import math

import torch
import torch.nn.functional as F
from comfy_execution.graph_utils import is_link
from nodes import PreviewImage


class EquirectangularPreview(PreviewImage):
    """Preview an LDR equirectangular image in an interactive Lat-Long viewer."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "view_width": (
                    "INT",
                    {"default": 1024, "min": 64, "max": 8192, "step": 8},
                ),
                "view_height": (
                    "INT",
                    {"default": 1024, "min": 64, "max": 8192, "step": 8},
                ),
                "view_yaw": (
                    "FLOAT",
                    {"default": 0.0, "min": -180.0, "max": 180.0, "step": 0.1},
                ),
                "view_pitch": (
                    "FLOAT",
                    {"default": 0.0, "min": -89.4, "max": 89.4, "step": 0.1},
                ),
                "view_fov": (
                    "FLOAT",
                    {"default": 75.0, "min": 25.0, "max": 110.0, "step": 0.1},
                ),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
                "dynprompt": "DYNPROMPT",
                "unique_id": "UNIQUE_ID",
            },
        }

    CATEGORY = "image"
    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("image", "view")
    FUNCTION = "preview_equirectangular"
    OUTPUT_NODE = True
    DESCRIPTION = (
        "Interactively previews an LDR equirectangular/Lat-Long image. The view output renders "
        "the current yaw, pitch, and field of view when connected."
    )
    SEARCH_ALIASES = ["panorama", "lat long", "lat-long", "360 preview", "equirectangular viewer"]

    @staticmethod
    def _output_is_connected(dynprompt, unique_id, output_index):
        if dynprompt is None or unique_id is None:
            return True
        source_id = str(unique_id)
        for node_id in dynprompt.all_node_ids():
            node = dynprompt.get_node(node_id)
            for value in node.get("inputs", {}).values():
                if is_link(value) and value[0] == source_id and int(value[1]) == output_index:
                    return True
        return False

    @staticmethod
    def render_view(image, width, height, yaw, pitch, fov):
        """Project a ComfyUI IMAGE batch with the same camera math as the WebGL viewer."""
        width = int(width)
        height = int(height)
        if width < 1 or height < 1:
            raise ValueError("Equirectangular view dimensions must be positive")

        device = image.device
        work = image.to(dtype=torch.float32)
        x = ((torch.arange(width, device=device, dtype=torch.float32) + 0.5) / width) * 2.0 - 1.0
        y = 1.0 - ((torch.arange(height, device=device, dtype=torch.float32) + 0.5) / height) * 2.0
        point_y, point_x = torch.meshgrid(y, x, indexing="ij")
        point_x = point_x * (width / height)

        tangent = math.tan(math.radians(float(fov)) * 0.5)
        ray_x = point_x * tangent
        ray_y = point_y * tangent
        ray_z = -torch.ones_like(ray_x)
        inverse_length = torch.rsqrt(ray_x.square() + ray_y.square() + ray_z.square())
        ray_x = ray_x * inverse_length
        ray_y = ray_y * inverse_length
        ray_z = ray_z * inverse_length

        pitch_radians = math.radians(float(pitch))
        pitch_cos = math.cos(pitch_radians)
        pitch_sin = math.sin(pitch_radians)
        pitched_y = pitch_cos * ray_y - pitch_sin * ray_z
        pitched_z = pitch_sin * ray_y + pitch_cos * ray_z

        yaw_radians = math.radians(float(yaw))
        yaw_cos = math.cos(yaw_radians)
        yaw_sin = math.sin(yaw_radians)
        rotated_x = yaw_cos * ray_x + yaw_sin * pitched_z
        rotated_z = -yaw_sin * ray_x + yaw_cos * pitched_z

        longitude = torch.atan2(rotated_x, -rotated_z)
        latitude = torch.asin(pitched_y.clamp(-1.0, 1.0))
        u = torch.remainder(longitude / (2.0 * math.pi) + 0.5, 1.0)
        v = 0.5 - latitude / math.pi

        source_width = work.shape[2]
        padded = torch.cat((work[:, :, -1:], work, work[:, :, :1]), dim=2)
        grid_x = 2.0 * (u * source_width + 1.0) / (source_width + 2.0) - 1.0
        grid_y = v * 2.0 - 1.0
        grid = torch.stack((grid_x, grid_y), dim=-1).unsqueeze(0).expand(work.shape[0], -1, -1, -1)
        projected = F.grid_sample(
            padded.permute(0, 3, 1, 2),
            grid,
            mode="bilinear",
            padding_mode="border",
            align_corners=False,
        )
        return projected.permute(0, 2, 3, 1).to(dtype=image.dtype)

    def preview_equirectangular(
        self,
        image,
        view_width=1024,
        view_height=1024,
        view_yaw=0.0,
        view_pitch=0.0,
        view_fov=75.0,
        prompt=None,
        extra_pnginfo=None,
        dynprompt=None,
        unique_id=None,
    ):
        result = self.save_images(
            image,
            filename_prefix="pepe_equirectangular_preview",
            prompt=prompt,
            extra_pnginfo=extra_pnginfo,
        )
        view = None
        if self._output_is_connected(dynprompt, unique_id, 1):
            view = self.render_view(
                image,
                view_width,
                view_height,
                view_yaw,
                view_pitch,
                view_fov,
            )
        result["result"] = (image, view)
        return result


NODE_CLASS_MAPPINGS = {
    "EquirectangularPreview": EquirectangularPreview,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "EquirectangularPreview": "Pepe Equirectangular Preview",
}
