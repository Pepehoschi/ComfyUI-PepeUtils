from nodes import PreviewImage


class EquirectangularPreview(PreviewImage):
    """Preview an LDR equirectangular image in an interactive Lat-Long viewer."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    CATEGORY = "image"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "preview_equirectangular"
    OUTPUT_NODE = True
    DESCRIPTION = "Interactively previews an LDR equirectangular/Lat-Long image. Drag to look around and use the mouse wheel to zoom."
    SEARCH_ALIASES = ["panorama", "lat long", "lat-long", "360 preview", "equirectangular viewer"]

    def preview_equirectangular(self, image, prompt=None, extra_pnginfo=None):
        return self.save_images(
            image,
            filename_prefix="pepe_equirectangular_preview",
            prompt=prompt,
            extra_pnginfo=extra_pnginfo,
        )


NODE_CLASS_MAPPINGS = {
    "EquirectangularPreview": EquirectangularPreview,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "EquirectangularPreview": "Pepe Equirectangular Preview",
}
