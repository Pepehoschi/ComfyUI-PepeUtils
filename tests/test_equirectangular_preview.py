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
    class FakeDynamicPrompt:
        def __init__(self, nodes):
            self.nodes = nodes

        def all_node_ids(self):
            return self.nodes.keys()

        def get_node(self, node_id):
            return self.nodes[node_id]

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
                dynprompt=self.FakeDynamicPrompt({}),
                unique_id="7",
            )

        self.assertIs(result, saved)
        self.assertIs(result["result"][0], image)
        self.assertIsNone(result["result"][1])
        save_images.assert_called_once_with(
            image,
            filename_prefix="pepe_equirectangular_preview",
            prompt={"node": "value"},
            extra_pnginfo={"workflow": {}},
        )

    def test_contract_is_preview_output_with_image_passthrough(self):
        inputs = EquirectangularPreview.INPUT_TYPES()
        self.assertEqual(inputs["required"]["image"][0], "IMAGE")
        self.assertEqual(inputs["required"]["view_width"][1]["default"], 1024)
        self.assertEqual(inputs["required"]["view_height"][1]["default"], 1024)
        self.assertEqual(EquirectangularPreview.RETURN_TYPES, ("IMAGE", "IMAGE"))
        self.assertEqual(EquirectangularPreview.RETURN_NAMES, ("image", "view"))
        self.assertTrue(EquirectangularPreview.OUTPUT_NODE)

    def test_view_output_connection_is_detected_from_prompt_links(self):
        connected = self.FakeDynamicPrompt(
            {"9": {"inputs": {"images": ["7", 1]}, "class_type": "PreviewImage"}}
        )
        unconnected = self.FakeDynamicPrompt(
            {"9": {"inputs": {"images": ["7", 0]}, "class_type": "PreviewImage"}}
        )

        self.assertTrue(EquirectangularPreview._output_is_connected(connected, "7", 1))
        self.assertFalse(EquirectangularPreview._output_is_connected(unconnected, "7", 1))

    def test_current_view_is_projected_at_requested_size(self):
        panorama = torch.rand((2, 24, 48, 3), dtype=torch.float32)

        view = EquirectangularPreview.render_view(
            panorama,
            width=40,
            height=32,
            yaw=37.0,
            pitch=-12.0,
            fov=80.0,
        )

        self.assertEqual(view.shape, (2, 32, 40, 3))
        self.assertEqual(view.dtype, panorama.dtype)
        self.assertTrue(torch.isfinite(view).all())

    def test_connected_view_is_returned_with_original_passthrough(self):
        panorama = torch.rand((1, 12, 24, 3), dtype=torch.float32)
        saved = {"ui": {"images": []}, "result": (panorama,)}
        prompt = self.FakeDynamicPrompt(
            {"9": {"inputs": {"images": ["7", 1]}, "class_type": "PreviewImage"}}
        )

        with mock.patch.object(preview_mod.PreviewImage, "save_images", return_value=saved):
            result = EquirectangularPreview().preview_equirectangular(
                panorama,
                view_width=20,
                view_height=16,
                dynprompt=prompt,
                unique_id="7",
            )

        self.assertIs(result["result"][0], panorama)
        self.assertEqual(result["result"][1].shape, (1, 16, 20, 3))

    def test_interaction_redraws_are_frame_limited_and_local(self):
        source = (ROOT / "web" / "equirectangular_preview.js").read_text(encoding="utf-8")

        self.assertIn("globalThis.requestAnimationFrame(drawNow)", source)
        self.assertIn("globalThis.cancelAnimationFrame(drawFrame)", source)
        self.assertIn("syncViewWidgets()", source)
        self.assertIn('const VIEW_STATE_WIDGETS = ["view_yaw", "view_pitch", "view_fov"]', source)
        self.assertNotIn("setDirtyCanvas", source)


if __name__ == "__main__":
    unittest.main()
