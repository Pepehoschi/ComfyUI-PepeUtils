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

spec = importlib.util.spec_from_file_location(
    "pepeutils_test",
    ROOT / "__init__.py",
    submodule_search_locations=[str(ROOT)],
)
pkg = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pkg
spec.loader.exec_module(pkg)

resize_mod = sys.modules["pepeutils_test.PepeResizeImage"]
PepeResizeImage = resize_mod.PepeResizeImage


class GeometryTests(unittest.TestCase):
    def test_align_down(self):
        self.assertEqual(resize_mod.align_down(1080, 32), 1056)
        self.assertEqual(resize_mod.align_down(1024, 32), 1024)
        self.assertEqual(resize_mod.align_down(7, 8), 8)
        self.assertEqual(resize_mod.align_down(7, 1), 7)

    def test_zero_dimensions(self):
        self.assertEqual(resize_mod.resolve_requested_dimensions(0, 0, 640, 480), (640, 480))
        self.assertEqual(resize_mod.resolve_requested_dimensions(0, 240, 640, 480), (320, 240))
        self.assertEqual(resize_mod.resolve_requested_dimensions(320, 0, 640, 480), (320, 240))

    def test_resize_geometry_landscape_and_portrait(self):
        geo = resize_mod.calculate_geometry(1600, 900, 1024, 1024, "resize", 8)
        self.assertEqual((geo["canvas_w"], geo["canvas_h"]), (1024, 576))
        geo = resize_mod.calculate_geometry(900, 1600, 1024, 512, "resize", 16)
        self.assertEqual((geo["canvas_w"] % 16, geo["canvas_h"] % 16), (0, 0))
        self.assertLessEqual(geo["canvas_w"], 1024)
        self.assertLessEqual(geo["canvas_h"], 512)

    def test_fixed_canvas_geometry(self):
        for mode in ("stretch", "pad", "pad_edge", "pad_edge_pixel", "crop", "pillarbox_blur"):
            geo = resize_mod.calculate_geometry(640, 480, 1001, 777, mode, 32)
            self.assertEqual((geo["canvas_w"], geo["canvas_h"]), (992, 768))

    def test_total_pixels_geometry(self):
        for source_w, source_h in ((1000, 1000), (1600, 900), (900, 1600)):
            geo = resize_mod.calculate_geometry(source_w, source_h, 1024, 1024, "total_pixels", 8)
            self.assertEqual(geo["canvas_w"] % 8, 0)
            self.assertEqual(geo["canvas_h"] % 8, 0)
            self.assertGreater(geo["canvas_w"] * geo["canvas_h"], 900_000)


class RoutingTests(unittest.TestCase):
    def test_real_downscale_path_uses_shared_sharper_preset(self):
        image = torch.linspace(0.0, 1.0, 32 * 32 * 3, dtype=torch.float32).reshape(1, 32, 32, 3)

        output = resize_mod.resize_photoshop_bicubic_sharper(image, 16, 16)

        self.assertEqual(output.shape, (1, 16, 16, 3))
        self.assertEqual(output.dtype, image.dtype)
        self.assertGreaterEqual(float(output.min()), 0.0)
        self.assertLessEqual(float(output.max()), 1.0)

    def test_dispatch_routes_upscale_downscale_unchanged_and_mixed(self):
        image = torch.zeros((1, 16, 16, 3), dtype=torch.float32)

        with mock.patch.object(resize_mod, "_resize_lanczos", side_effect=lambda img, w, h: torch.zeros((1, h, w, 3))) as lanczos:
            with mock.patch.object(resize_mod, "resize_photoshop_bicubic_sharper", side_effect=lambda img, w, h: torch.zeros((1, h, w, 3))) as sharp:
                resize_mod.resize_image_auto(image, 32, 32)
                self.assertEqual(lanczos.call_count, 1)
                self.assertEqual(sharp.call_count, 0)

                lanczos.reset_mock()
                sharp.reset_mock()
                resize_mod.resize_image_auto(image, 8, 8)
                self.assertEqual(lanczos.call_count, 0)
                self.assertEqual(sharp.call_count, 1)

                lanczos.reset_mock()
                sharp.reset_mock()
                same = resize_mod.resize_image_auto(image, 16, 16)
                self.assertIs(same, image)
                self.assertEqual(lanczos.call_count, 0)
                self.assertEqual(sharp.call_count, 0)

                resize_mod.resize_image_auto(image, 8, 32)
                self.assertGreaterEqual(sharp.call_count, 1)
                self.assertGreaterEqual(lanczos.call_count, 1)


class NodeModeTests(unittest.TestCase):
    def setUp(self):
        self.node = PepeResizeImage()

    def image(self, batch=2, height=24, width=32):
        return torch.linspace(0.0, 1.0, batch * height * width * 3, dtype=torch.float32).reshape(batch, height, width, 3)

    def mask(self, batch=2, height=24, width=32):
        return torch.linspace(0.0, 1.0, batch * height * width, dtype=torch.float32).reshape(batch, height, width)

    def run_mode(self, mode, width=64, height=40, stride=8, crop_position="center", mask=None):
        return self.node.resize(
            self.image(),
            width,
            height,
            mode,
            10,
            20,
            30,
            crop_position,
            stride,
            mask=mask,
        )

    def assert_valid(self, result, batch=2, stride=8):
        image, width, height, mask = result
        self.assertEqual(image.shape[0], batch)
        self.assertEqual(mask.shape[0], batch)
        self.assertEqual((image.shape[2], image.shape[1]), (width, height))
        self.assertEqual(mask.shape[-2:], (height, width))
        self.assertEqual(width % stride, 0)
        self.assertEqual(height % stride, 0)
        self.assertGreaterEqual(float(image.min()), 0.0)
        self.assertLessEqual(float(image.max()), 1.0)
        self.assertGreaterEqual(float(mask.min()), 0.0)
        self.assertLessEqual(float(mask.max()), 1.0)

    def test_all_modes_return_valid_tensors(self):
        for mode in resize_mod.KEEP_PROPORTION_MODES:
            with self.subTest(mode=mode):
                result = self.run_mode(mode, mask=self.mask())
                self.assert_valid(result)

    def test_stretch_reaches_exact_canvas(self):
        image, width, height, mask = self.run_mode("stretch", width=65, height=41, stride=8, mask=self.mask())
        self.assertEqual((width, height), (64, 40))
        self.assertEqual(image.shape[1:3], (40, 64))
        self.assertEqual(mask.shape[-2:], (40, 64))

    def test_resize_preserves_aspect_without_padding(self):
        image, width, height, mask = self.run_mode("resize", width=64, height=64, stride=8, mask=self.mask())
        self.assertEqual((width, height), (64, 48))
        self.assertEqual(image.shape[1:3], (48, 64))

    def test_pad_modes_fill_canvas(self):
        for mode in ("pad", "pad_edge", "pad_edge_pixel"):
            with self.subTest(mode=mode):
                image, width, height, mask = self.run_mode(mode, width=64, height=64, stride=8, mask=self.mask())
                self.assertEqual((width, height), (64, 64))
                self.assertEqual(image.shape[1:3], (64, 64))
                self.assertEqual(mask.shape[-2:], (64, 64))

    def test_pad_color_appears_in_padding(self):
        image, _width, _height, _mask = self.run_mode("pad", width=64, height=64, stride=8)
        self.assertTrue(torch.allclose(image[0, 0, 0], torch.tensor([10 / 255, 20 / 255, 30 / 255]), atol=1e-5))

    def test_pad_edge_pixel_repeats_border_pixels(self):
        image = torch.zeros((1, 2, 2, 3), dtype=torch.float32)
        image[:, 0, 0, :] = 0.1
        image[:, 0, 1, :] = 0.2
        image[:, 1, 0, :] = 0.3
        image[:, 1, 1, :] = 0.4
        out_image, width, height, _mask = self.node.resize(
            image,
            4,
            8,
            "pad_edge_pixel",
            0,
            0,
            0,
            "center",
            1,
        )
        self.assertEqual((width, height), (4, 8))
        self.assertTrue(torch.allclose(out_image[:, 0, 0, :], out_image[:, 2, 0, :]))
        self.assertTrue(torch.allclose(out_image[:, -1, -1, :], out_image[:, 5, -1, :]))

    def test_crop_positions_preserve_dimensions(self):
        for position in resize_mod.CROP_POSITIONS:
            with self.subTest(position=position):
                result = self.run_mode("crop", width=48, height=64, stride=8, crop_position=position, mask=self.mask())
                self.assert_valid(result)
                self.assertEqual(result[0].shape[1:3], (64, 48))

    def test_crop_position_top_and_bottom_preserve_expected_side(self):
        image = torch.zeros((1, 20, 10, 3), dtype=torch.float32)
        image[:, :10, :, :] = 0.25
        image[:, 10:, :, :] = 0.75
        top_image, _w, _h, _m = self.node.resize(image, 10, 10, "crop", 0, 0, 0, "top", 1)
        bottom_image, _w, _h, _m = self.node.resize(image, 10, 10, "crop", 0, 0, 0, "bottom", 1)
        self.assertLess(float(top_image.mean()), float(bottom_image.mean()))

    def test_single_mask_broadcasts_to_batch(self):
        single_mask = self.mask(batch=1)
        image, width, height, mask = self.run_mode("pad", mask=single_mask)
        self.assertEqual(mask.shape[0], image.shape[0])
        self.assertEqual(mask.shape[-2:], (height, width))

    def test_no_mask_returns_default_mask(self):
        image, width, height, mask = self.run_mode("resize", mask=None)
        self.assertEqual(mask.shape, (image.shape[0], height, width))
        self.assertEqual(float(mask.max()), 0.0)


if __name__ == "__main__":
    unittest.main()
