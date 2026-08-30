from .AnimePromptGen import AnimePromptGen
from .CubemapProjection import EquirectangularToCubemapStrip, EquirectangularToCylindrical
from .EquirectangularPreview import EquirectangularPreview
from .LoadImageCropped import LoadImageCropped
from .PasteImage import PasteImage
from .PepeBreak import PepeBreak
from .PepeConsolePrint import PepeConsolePrint
from .PepeImageFilter import PepeImageFilter
from .PepeLazyRoute import PepeLazyRoute, PepeRouteSplit
from .PepeLoadImagesFromFolder import PepeLoadImagesFromFolder
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
    "PepeBreak": PepeBreak,
    "PepeConsolePrint": PepeConsolePrint,
    "PepeImageFilter": PepeImageFilter,
    "PepeLazyRoute": PepeLazyRoute,
    "PepeLoadImagesFromFolder": PepeLoadImagesFromFolder,
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
    "PepeBreak": "Pepe Break",
    "PepeConsolePrint": "Pepe Console Print",
    "PepeImageFilter": "Pepe Image Filter",
    "PepeLazyRoute": "Pepe Lazy Route",
    "PepeLoadImagesFromFolder": "Pepe Load Images From Folder",
    "PepeRouteSplit": "Pepe Route Split",
    "PepeResizeImage": "Pepe Resize Image",
    "PepeScaleImageBy": "Pepe Scale Image By",
    "StrideScaleSize": "Stride Scale Size",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
