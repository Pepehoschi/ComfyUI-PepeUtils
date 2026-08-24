import hashlib
import os
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps


SUPPORTED_IMAGE_EXTENSIONS = {
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}


def _resolve_folder(folder):
    value = str(folder).strip()
    if not value:
        raise ValueError("Image folder is required.")
    return Path(os.path.expandvars(os.path.expanduser(value))).resolve()


def _image_paths(folder):
    root = _resolve_folder(folder)
    if not root.is_dir():
        raise ValueError(f"Image folder does not exist or is not a directory: {root}")

    return sorted(
        (
            path
            for path in root.iterdir()
            if path.is_file() and path.suffix.casefold() in SUPPORTED_IMAGE_EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )


def _load_image(path):
    with Image.open(path) as source:
        source.seek(0)
        image = ImageOps.exif_transpose(source)
        width, height = image.size
        image_tensor = torch.from_numpy(
            np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        ).unsqueeze(0)

        if "A" in image.getbands():
            alpha = np.asarray(image.getchannel("A"), dtype=np.float32) / 255.0
            mask_tensor = 1.0 - torch.from_numpy(alpha)
        elif image.mode == "P" and "transparency" in image.info:
            alpha = np.asarray(image.convert("RGBA").getchannel("A"), dtype=np.float32) / 255.0
            mask_tensor = 1.0 - torch.from_numpy(alpha)
        else:
            mask_tensor = torch.zeros((height, width), dtype=torch.float32)

    return image_tensor, mask_tensor.unsqueeze(0)


class PepeLoadImagesFromFolder:
    """Load folder images as synchronized image, mask, and filename lists."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": ("STRING", {"default": "", "multiline": False}),
                "image_load_cap": ("INT", {"default": 0, "min": 0, "max": 999999, "step": 1}),
                "select_every_nth": ("INT", {"default": 1, "min": 1, "max": 999999, "step": 1}),
            },
        }

    CATEGORY = "Pepe Utils/image"
    RETURN_TYPES = ("IMAGE", "MASK", "STRING", "INT")
    RETURN_NAMES = ("images", "masks", "file_name", "image_count")
    OUTPUT_IS_LIST = (True, True, True, False)
    FUNCTION = "load_images"
    DESCRIPTION = (
        "Loads images from an arbitrary folder as synchronized lists. Each filename includes its "
        "original extension so downstream text nodes can derive sidecar names."
    )

    def load_images(self, folder, image_load_cap=0, select_every_nth=1):
        selected_paths = _image_paths(folder)[:: int(select_every_nth)]
        if image_load_cap > 0:
            selected_paths = selected_paths[: int(image_load_cap)]
        if not selected_paths:
            raise ValueError(f"No supported images found in folder: {_resolve_folder(folder)}")

        images = []
        masks = []
        filenames = []
        for path in selected_paths:
            image, mask = _load_image(path)
            images.append(image)
            masks.append(mask)
            filenames.append(path.name)

        return images, masks, filenames, len(selected_paths)

    @classmethod
    def IS_CHANGED(cls, folder, image_load_cap=0, select_every_nth=1):
        digest = hashlib.sha256()
        selected_paths = _image_paths(folder)[:: int(select_every_nth)]
        if image_load_cap > 0:
            selected_paths = selected_paths[: int(image_load_cap)]
        for path in selected_paths:
            stat = path.stat()
            digest.update(path.name.encode("utf-8"))
            digest.update(f"|{stat.st_size}|{stat.st_mtime_ns}".encode("ascii"))
        return digest.hexdigest()

    @classmethod
    def VALIDATE_INPUTS(cls, folder, image_load_cap=0, select_every_nth=1):
        try:
            root = _resolve_folder(folder)
        except ValueError as error:
            return str(error)
        if not root.is_dir():
            return f"Image folder does not exist or is not a directory: {root}"
        return True


NODE_CLASS_MAPPINGS = {
    "PepeLoadImagesFromFolder": PepeLoadImagesFromFolder,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PepeLoadImagesFromFolder": "Pepe Load Images From Folder",
}
