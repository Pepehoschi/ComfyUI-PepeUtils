from .LoadImageCropped import LoadImageCropped
from .StrideScaleSize import StrideScaleSize

WEB_DIRECTORY = "./web"

NODE_CLASS_MAPPINGS = {
    "LoadImageCropped": LoadImageCropped,
    "StrideScaleSize": StrideScaleSize,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadImageCropped": "Load Image Cropped",
    "StrideScaleSize": "Stride Scale Size",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
