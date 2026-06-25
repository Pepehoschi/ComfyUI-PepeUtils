from .AnimePromptGen import AnimePromptGen
from .LoadImageCropped import LoadImageCropped
from .PepeScaleImageBy import PepeScaleImageBy
from .StrideScaleSize import StrideScaleSize

WEB_DIRECTORY = "./web"

NODE_CLASS_MAPPINGS = {
    "AnimePromptGen": AnimePromptGen,
    "LoadImageCropped": LoadImageCropped,
    "PepeScaleImageBy": PepeScaleImageBy,
    "StrideScaleSize": StrideScaleSize,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AnimePromptGen": "Anime PromptGen",
    "LoadImageCropped": "Load Image Cropped",
    "PepeScaleImageBy": "Pepe Scale Image By",
    "StrideScaleSize": "Stride Scale Size",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
