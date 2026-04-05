import hashlib
import os

import numpy as np
import torch
from PIL import Image, ImageOps, ImageSequence

import comfy.model_management
import folder_paths
import node_helpers


class LoadImageCropped:
    @classmethod
    def INPUT_TYPES(cls):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files = folder_paths.filter_files_content_types(files, ["image"])
        return {
            "required": {
                "image": (sorted(files), {"image_upload": True}),
                "x1": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "y1": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "x2": ("INT", {"default": 0, "min": 0, "advanced": True}),
                "y2": ("INT", {"default": 0, "min": 0, "advanced": True}),
            },
        }

    CATEGORY = "image"
    RETURN_TYPES = ("IMAGE", "MASK", "INT", "INT")
    RETURN_NAMES = ("image", "mask", "width", "height")
    FUNCTION = "load_image"

    @staticmethod
    def _normalize_crop(x1, y1, x2, y2, width, height):
        left = max(0, min(int(x1), int(x2)))
        top = max(0, min(int(y1), int(y2)))
        right = min(width, max(int(x1), int(x2)))
        bottom = min(height, max(int(y1), int(y2)))

        if right <= left or bottom <= top:
            return (0, 0, width, height)

        return (left, top, right, bottom)

    def load_image(self, image, x1=0, y1=0, x2=0, y2=0):
        image_path = folder_paths.get_annotated_filepath(image)

        img = node_helpers.pillow(Image.open, image_path)

        output_images = []
        output_masks = []
        w, h = None, None

        dtype = comfy.model_management.intermediate_dtype()

        for i in ImageSequence.Iterator(img):
            i = node_helpers.pillow(ImageOps.exif_transpose, i)

            if i.mode == "I":
                i = i.point(lambda value: value * (1 / 255))
            image_rgb = i.convert("RGB")

            if len(output_images) == 0:
                w = image_rgb.size[0]
                h = image_rgb.size[1]

            if image_rgb.size[0] != w or image_rgb.size[1] != h:
                continue

            image_np = np.array(image_rgb).astype(np.float32) / 255.0
            image_tensor = torch.from_numpy(image_np)[None,]

            if "A" in i.getbands():
                mask = np.array(i.getchannel("A")).astype(np.float32) / 255.0
                mask = 1.0 - torch.from_numpy(mask)
            elif i.mode == "P" and "transparency" in i.info:
                mask = np.array(i.convert("RGBA").getchannel("A")).astype(np.float32) / 255.0
                mask = 1.0 - torch.from_numpy(mask)
            else:
                mask = torch.zeros((h, w), dtype=torch.float32, device="cpu")

            output_images.append(image_tensor.to(dtype=dtype))
            output_masks.append(mask.unsqueeze(0).to(dtype=dtype))

            if img.format == "MPO":
                break

        if len(output_images) > 1:
            output_image = torch.cat(output_images, dim=0)
            output_mask = torch.cat(output_masks, dim=0)
        else:
            output_image = output_images[0]
            output_mask = output_masks[0]

        left, top, right, bottom = self._normalize_crop(x1, y1, x2, y2, w, h)
        output_image = output_image[:, top:bottom, left:right, :]
        output_mask = output_mask[:, top:bottom, left:right]
        crop_width = right - left
        crop_height = bottom - top

        return (output_image, output_mask, crop_width, crop_height)

    @classmethod
    def IS_CHANGED(cls, image, x1=0, y1=0, x2=0, y2=0):
        image_path = folder_paths.get_annotated_filepath(image)
        m = hashlib.sha256()
        with open(image_path, "rb") as f:
            m.update(f.read())
        m.update(f"|{int(x1)}|{int(y1)}|{int(x2)}|{int(y2)}".encode("utf-8"))
        return m.digest().hex()

    @classmethod
    def VALIDATE_INPUTS(cls, image, x1=0, y1=0, x2=0, y2=0):
        if not folder_paths.exists_annotated_filepath(image):
            return "Invalid image file: {}".format(image)

        for value_name, value in (("x1", x1), ("y1", y1), ("x2", x2), ("y2", y2)):
            if int(value) < 0:
                return f"{value_name} must be >= 0"

        return True


NODE_CLASS_MAPPINGS = {
    "LoadImageCropped": LoadImageCropped,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadImageCropped": "Load Image Cropped",
}
