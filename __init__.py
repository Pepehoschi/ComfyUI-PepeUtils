from .AnimePromptGen import AnimePromptGen
from .LoadImageCropped import LoadImageCropped
from .PasteImage import PasteImage
from .PepeResizeImage import PepeResizeImage
from .PepeScaleImageBy import PepeScaleImageBy
from .StrideScaleSize import StrideScaleSize

WEB_DIRECTORY = "./web"

NODE_CLASS_MAPPINGS = {
    "AnimePromptGen": AnimePromptGen,
    "LoadImageCropped": LoadImageCropped,
    "PasteImage": PasteImage,
    "PepeResizeImage": PepeResizeImage,
    "PepeScaleImageBy": PepeScaleImageBy,
    "StrideScaleSize": StrideScaleSize,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AnimePromptGen": "Anime PromptGen",
    "LoadImageCropped": "Load Image Cropped",
    "PasteImage": "Pepe Paste Image",
    "PepeResizeImage": "Pepe Resize Image",
    "PepeScaleImageBy": "Pepe Scale Image By",
    "StrideScaleSize": "Stride Scale Size",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
