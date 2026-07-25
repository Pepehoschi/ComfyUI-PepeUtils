import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import torch
from PIL import Image


ROOT = pathlib.Path(__file__).resolve().parents[1]
COMFY_ROOT = ROOT.parents[1]
if str(COMFY_ROOT) not in sys.path:
    sys.path.insert(0, str(COMFY_ROOT))

PACKAGE_NAME = "pepeutils_paste_test"
if PACKAGE_NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE_NAME] = package
    spec.loader.exec_module(package)

paste_mod = sys.modules[f"{PACKAGE_NAME}.PasteImage"]
load_mod = sys.modules[f"{PACKAGE_NAME}.LoadImageCropped"]
PasteImage = paste_mod.PasteImage


class PasteImageTests(unittest.TestCase):
    def test_node_is_registered(self):
        package = sys.modules[PACKAGE_NAME]
        self.assertIs(package.NODE_CLASS_MAPPINGS["PasteImage"], PasteImage)
        self.assertEqual(package.NODE_DISPLAY_NAME_MAPPINGS["PasteImage"], "Pepe Paste Image")

    def test_input_is_an_internal_string_and_outputs_match_load_image(self):
        image_spec = PasteImage.INPUT_TYPES()["required"]["image"]
        self.assertEqual(image_spec[0], "STRING")
        self.assertEqual(PasteImage.RETURN_TYPES, ("IMAGE", "MASK"))

    def test_validation_requires_an_existing_temp_image(self):
        self.assertIn("Paste an image", PasteImage.VALIDATE_INPUTS(""))
        self.assertIn("temp directory", PasteImage.VALIDATE_INPUTS("persistent.png"))

        with mock.patch.object(paste_mod.LoadImageCropped, "VALIDATE_INPUTS", return_value=True) as validate:
            self.assertTrue(PasteImage.VALIDATE_INPUTS("paste/image.png [temp]"))
            validate.assert_called_once_with("paste/image.png [temp]")

    def test_loads_rgb_image_and_zero_mask(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "clipboard.png"
            Image.new("RGB", (3, 2), (64, 128, 255)).save(path)

            with mock.patch.object(load_mod.folder_paths, "get_annotated_filepath", return_value=str(path)):
                with mock.patch.object(
                    load_mod.comfy.model_management,
                    "intermediate_dtype",
                    return_value=torch.float32,
                ):
                    image, mask = PasteImage().load_image("clipboard.png [temp]")

        self.assertEqual(tuple(image.shape), (1, 2, 3, 3))
        self.assertEqual(tuple(mask.shape), (1, 2, 3))
        self.assertTrue(torch.allclose(image[0, 0, 0], torch.tensor([64, 128, 255]) / 255))
        self.assertEqual(float(mask.max()), 0.0)

    def test_preserves_alpha_as_comfyui_inverted_mask(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "clipboard.png"
            source = Image.new("RGBA", (2, 1), (255, 0, 0, 255))
            source.putpixel((1, 0), (255, 0, 0, 0))
            source.save(path)

            with mock.patch.object(load_mod.folder_paths, "get_annotated_filepath", return_value=str(path)):
                with mock.patch.object(
                    load_mod.comfy.model_management,
                    "intermediate_dtype",
                    return_value=torch.float32,
                ):
                    _, mask = PasteImage().load_image("clipboard.png [temp]")

        self.assertEqual(mask[0, 0, 0].item(), 0.0)
        self.assertEqual(mask[0, 0, 1].item(), 1.0)

    def test_change_token_tracks_file_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "clipboard.png"
            path.write_bytes(b"first")
            with mock.patch.object(load_mod.folder_paths, "get_annotated_filepath", return_value=str(path)):
                first = PasteImage.IS_CHANGED("clipboard.png [temp]")
                path.write_bytes(b"second")
                second = PasteImage.IS_CHANGED("clipboard.png [temp]")

        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
