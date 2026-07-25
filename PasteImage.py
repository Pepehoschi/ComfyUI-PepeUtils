from .LoadImageCropped import LoadImageCropped


class PasteImage(LoadImageCropped):
    """Load an image uploaded to ComfyUI's session-scoped temp directory."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("STRING", {"default": ""}),
            },
        }

    CATEGORY = "image"
    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "mask")
    FUNCTION = "load_image"
    DESCRIPTION = "Paste an image from the clipboard. Images are stored only in ComfyUI's temp directory."

    def load_image(self, image):
        output_image, output_mask, _, _ = super().load_image(image)
        return (output_image, output_mask)

    @classmethod
    def IS_CHANGED(cls, image):
        return super().IS_CHANGED(image)

    @classmethod
    def VALIDATE_INPUTS(cls, image):
        if not image:
            return "Paste an image into the node before running the workflow."
        if not image.rstrip().endswith("[temp]"):
            return "Paste Image only accepts images stored in ComfyUI's temp directory."
        return super().VALIDATE_INPUTS(image)


NODE_CLASS_MAPPINGS = {
    "PasteImage": PasteImage,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PasteImage": "Pepe Paste Image",
}
