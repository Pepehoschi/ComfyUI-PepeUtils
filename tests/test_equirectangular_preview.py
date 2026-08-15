import importlib.util
import pathlib
import sys
import unittest
from unittest import mock

import torch


ROOT = pathlib.Path(__file__).resolve().parents[1]
COMFY_ROOT = ROOT.parents[1]
if str(COMFY_ROOT) not in sys.path:
    sys.path.insert(0, str(COMFY_ROOT))

PACKAGE_NAME = "pepeutils_equirectangular_test"
if PACKAGE_NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE_NAME] = package
    spec.loader.exec_module(package)

preview_mod = sys.modules[f"{PACKAGE_NAME}.EquirectangularPreview"]
EquirectangularPreview = preview_mod.EquirectangularPreview


class EquirectangularPreviewTests(unittest.TestCase):
    def test_node_is_registered_with_searchable_display_name(self):
        package = sys.modules[PACKAGE_NAME]
        self.assertIs(
            package.NODE_CLASS_MAPPINGS["EquirectangularPreview"],
            EquirectangularPreview,
        )
        self.assertEqual(
            package.NODE_DISPLAY_NAME_MAPPINGS["EquirectangularPreview"],
            "Pepe Equirectangular Preview",
        )

    def test_accepts_and_passes_through_regular_image_tensor(self):
        image = torch.zeros((1, 64, 128, 3), dtype=torch.float32)
        saved = {"ui": {"images": [{"filename": "preview.png", "type": "temp"}]}, "result": (image,)}

        with mock.patch.object(preview_mod.PreviewImage, "save_images", return_value=saved) as save_images:
            result = EquirectangularPreview().preview_equirectangular(
                image,
                prompt={"node": "value"},
                extra_pnginfo={"workflow": {}},
            )

        self.assertIs(result, saved)
        self.assertIs(result["result"][0], image)
        save_images.assert_called_once_with(
            image,
            filename_prefix="pepe_equirectangular_preview",
            prompt={"node": "value"},
            extra_pnginfo={"workflow": {}},
        )

    def test_contract_is_preview_output_with_image_passthrough(self):
        inputs = EquirectangularPreview.INPUT_TYPES()
        self.assertEqual(inputs["required"]["image"][0], "IMAGE")
        self.assertEqual(EquirectangularPreview.RETURN_TYPES, ("IMAGE",))
        self.assertEqual(EquirectangularPreview.RETURN_NAMES, ("image",))
        self.assertTrue(EquirectangularPreview.OUTPUT_NODE)

    def test_interaction_redraws_are_frame_limited_and_local(self):
        source = (ROOT / "web" / "equirectangular_preview.js").read_text(encoding="utf-8")

        self.assertIn("globalThis.requestAnimationFrame(drawNow)", source)
        self.assertIn("globalThis.cancelAnimationFrame(drawFrame)", source)
        self.assertNotIn("setDirtyCanvas", source)


if __name__ == "__main__":
    unittest.main()
