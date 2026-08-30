"""Equirectangular panorama conversions to cubemap and cylindrical projections."""

import math

import torch

from .EquirectangularPreview import EquirectangularPreview


class EquirectangularToCubemapStrip:
    """Render perspective faces around the horizon as a tileable strip."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "face_size": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 8192,
                        "step": 8,
                        "tooltip": "Width of each face; 0 divides the panorama width by side_count",
                    },
                ),
                "side_count": (
                    "INT",
                    {
                        "default": 4,
                        "min": 2,
                        "max": 64,
                        "step": 1,
                        "tooltip": "Number of perspective faces around the horizon; 4 produces a cubemap strip",
                    },
                ),
                "vertical_fov": (
                    "FLOAT",
                    {
                        "default": 90.0,
                        "min": 1.0,
                        "max": 179.0,
                        "step": 1.0,
                        "tooltip": "Vertical field of view in degrees; face height is calculated automatically",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("cubemap_strip",)
    FUNCTION = "convert"
    CATEGORY = "PepeUtils/image"
    DESCRIPTION = (
        "Converts an equirectangular panorama into a horizontally tileable strip of perspective "
        "faces with configurable vertical coverage. Four sides produce a cubemap strip."
    )
    SEARCH_ALIASES = [
        "cubemap strip",
        "panorama to cubemap",
        "equirectangular cubemap",
        "four side cubemap",
        "prism strip",
        "panorama to prism",
    ]

    @staticmethod
    def resolve_face_size(image, face_size, side_count=4):
        requested = int(face_size)
        return requested if requested > 0 else max(1, int(image.shape[2]) // int(side_count))

    @classmethod
    def convert(cls, image, face_size=0, side_count=4, vertical_fov=90.0):
        count = int(side_count)
        if count < 2:
            raise ValueError("Cubemap strip side_count must be at least 2")
        vertical_fov = float(vertical_fov)
        if not 0.0 < vertical_fov < 180.0:
            raise ValueError("Cubemap strip vertical_fov must be between 0 and 180 degrees")
        size = cls.resolve_face_size(image, face_size, count)
        horizontal_scale = math.tan(math.pi / count)
        vertical_scale = math.tan(math.radians(vertical_fov) / 2.0)
        height = max(1, round(size * vertical_scale / horizontal_scale))
        device = image.device
        local_x = (
            (torch.arange(size, device=device, dtype=torch.float32) + 0.5) / size
        ) * 2.0 - 1.0
        local_y = 1.0 - (
            (torch.arange(height, device=device, dtype=torch.float32) + 0.5) / height
        ) * 2.0
        face_y, face_x = torch.meshgrid(local_y, local_x, indexing="ij")
        local_x = face_x * horizontal_scale
        local_y = face_y * vertical_scale

        # Each pinhole-camera face spans exactly one side of the regular prism.
        # Face zero looks forward; subsequent faces advance clockwise around the horizon.
        directions = []
        for face_index in range(count):
            yaw = face_index * (2.0 * math.pi / count)
            yaw_sin = math.sin(yaw)
            yaw_cos = math.cos(yaw)
            directions.append(
                (
                    yaw_sin + local_x * yaw_cos,
                    local_y,
                    -yaw_cos + local_x * yaw_sin,
                )
            )
        direction_x = torch.cat([direction[0] for direction in directions], dim=1)
        direction_y = torch.cat([direction[1] for direction in directions], dim=1)
        direction_z = torch.cat([direction[2] for direction in directions], dim=1)
        strip = EquirectangularPreview.sample_directions(
            image,
            direction_x,
            direction_y,
            direction_z,
        )
        return (strip,)


class EquirectangularToCylindrical:
    """Project a panorama onto a cylinder and unroll its side into a tileable image."""

    DEFAULT_MAX_LATITUDE = math.degrees(math.atan(math.pi / 2.0))

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "output_width": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 16384,
                        "step": 8,
                        "tooltip": "Output width; 0 preserves the panorama width",
                    },
                ),
                "output_height": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 16384,
                        "step": 8,
                        "tooltip": "Output height; 0 uses square distances on the cylinder surface",
                    },
                ),
                "max_latitude": (
                    "FLOAT",
                    {
                        "default": cls.DEFAULT_MAX_LATITUDE,
                        "min": 1.0,
                        "max": 89.0,
                        "step": 0.1,
                        "tooltip": "North/south latitude limit; poles cannot fit on a finite cylinder",
                    },
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("cylindrical",)
    FUNCTION = "convert"
    CATEGORY = "PepeUtils/image"
    DESCRIPTION = (
        "Projects an equirectangular panorama onto a vertical cylinder and unrolls the side into "
        "a seamless, horizontally tileable image."
    )
    SEARCH_ALIASES = [
        "cylindrical panorama",
        "equirectangular cylindrical",
        "panorama to cylinder",
        "cylinder projection",
    ]

    @classmethod
    def resolve_dimensions(cls, image, output_width, output_height, max_latitude):
        width = int(output_width) if int(output_width) > 0 else int(image.shape[2])
        latitude = float(max_latitude)
        if not 0.0 < latitude < 90.0:
            raise ValueError("Cylindrical max_latitude must be between 0 and 90 degrees")
        cylinder_half_height = math.tan(math.radians(latitude))
        height = int(output_height)
        if height <= 0:
            height = max(1, round(width * cylinder_half_height / math.pi))
        return width, height, cylinder_half_height

    @classmethod
    def convert(
        cls,
        image,
        output_width=0,
        output_height=0,
        max_latitude=DEFAULT_MAX_LATITUDE,
    ):
        width, height, half_height = cls.resolve_dimensions(
            image,
            output_width,
            output_height,
            max_latitude,
        )
        device = image.device
        longitude = (
            (torch.arange(width, device=device, dtype=torch.float32) + 0.5) / width
        ) * (2.0 * math.pi) - math.pi
        cylinder_y = half_height * (
            1.0
            - 2.0
            * (torch.arange(height, device=device, dtype=torch.float32) + 0.5)
            / height
        )
        direction_y, longitude_grid = torch.meshgrid(cylinder_y, longitude, indexing="ij")
        direction_x = torch.sin(longitude_grid)
        direction_z = -torch.cos(longitude_grid)
        cylindrical = EquirectangularPreview.sample_directions(
            image,
            direction_x,
            direction_y,
            direction_z,
        )
        return (cylindrical,)


NODE_CLASS_MAPPINGS = {
    "EquirectangularToCubemapStrip": EquirectangularToCubemapStrip,
    "EquirectangularToCylindrical": EquirectangularToCylindrical,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "EquirectangularToCubemapStrip": "Pepe Equirectangular to Cubemap Strip",
    "EquirectangularToCylindrical": "Pepe Equirectangular to Cylindrical",
}
