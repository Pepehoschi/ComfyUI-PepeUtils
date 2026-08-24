from .AnimePromptGen import AnimePromptGen
from .CubemapProjection import EquirectangularToCubemapStrip, EquirectangularToCylindrical
from .EquirectangularPreview import EquirectangularPreview
from .LoadImageCropped import LoadImageCropped
from .PasteImage import PasteImage
from .PepeLoadImagesFromFolder import PepeLoadImagesFromFolder
from .PepeImageFilter import PepeImageFilter
from .PepeLazyRoute import PepeLazyRoute, PepeRouteSplit
from .PepeResizeImage import PepeResizeImage
from .PepeScaleImageBy import PepeScaleImageBy
from .StrideScaleSize import StrideScaleSize

WEB_DIRECTORY = "./web"

NODE_CLASS_MAPPINGS = {
    "AnimePromptGen": AnimePromptGen,
    "EquirectangularToCubemapStrip": EquirectangularToCubemapStrip,
    "EquirectangularToCylindrical": EquirectangularToCylindrical,
    "EquirectangularPreview": EquirectangularPreview,
    "LoadImageCropped": LoadImageCropped,
    "PasteImage": PasteImage,
    "PepeLoadImagesFromFolder": PepeLoadImagesFromFolder,
    "PepeImageFilter": PepeImageFilter,
    "PepeLazyRoute": PepeLazyRoute,
    "PepeRouteSplit": PepeRouteSplit,
    "PepeResizeImage": PepeResizeImage,
    "PepeScaleImageBy": PepeScaleImageBy,
    "StrideScaleSize": StrideScaleSize,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AnimePromptGen": "Anime PromptGen",
    "EquirectangularToCubemapStrip": "Pepe Equirectangular to Cubemap Strip",
    "EquirectangularToCylindrical": "Pepe Equirectangular to Cylindrical",
    "EquirectangularPreview": "Pepe Equirectangular Preview",
    "LoadImageCropped": "Load Image Cropped",
    "PasteImage": "Pepe Paste Image",
    "PepeLoadImagesFromFolder": "Pepe Load Images From Folder",
    "PepeImageFilter": "Pepe Image Filter",
    "PepeLazyRoute": "Pepe Lazy Route",
    "PepeRouteSplit": "Pepe Route Split",
    "PepeResizeImage": "Pepe Resize Image",
    "PepeScaleImageBy": "Pepe Scale Image By",
    "StrideScaleSize": "Stride Scale Size",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
