import importlib.util
import math
import pathlib
import sys
import unittest

import torch


ROOT = pathlib.Path(__file__).resolve().parents[1]
COMFY_ROOT = ROOT.parents[1]
if str(COMFY_ROOT) not in sys.path:
    sys.path.insert(0, str(COMFY_ROOT))

PACKAGE_NAME = "pepeutils_cubemap_test"
if PACKAGE_NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE_NAME] = package
    spec.loader.exec_module(package)

package = sys.modules[PACKAGE_NAME]
CubemapStrip = package.NODE_CLASS_MAPPINGS["EquirectangularToCubemapStrip"]
Cylindrical = package.NODE_CLASS_MAPPINGS["EquirectangularToCylindrical"]


def directional_panorama(height=128, width=256):
    longitude = ((torch.arange(width, dtype=torch.float32) + 0.5) / width - 0.5) * (2 * math.pi)
    red = (torch.cos(longitude) + 1.0) * 0.5
    green = (torch.sin(longitude) + 1.0) * 0.5
    blue = torch.full_like(red, 0.25)
    row = torch.stack((red, green, blue), dim=-1)
    return row.unsqueeze(0).repeat(height, 1, 1).unsqueeze(0)


def cartesian_direction_panorama(height=256, width=512):
    longitude = ((torch.arange(width, dtype=torch.float32) + 0.5) / width - 0.5) * (2 * math.pi)
    latitude = math.pi * 0.5 - ((torch.arange(height, dtype=torch.float32) + 0.5) / height) * math.pi
    latitude_grid, longitude_grid = torch.meshgrid(latitude, longitude, indexing="ij")
    cos_latitude = torch.cos(latitude_grid)
    direction = torch.stack(
        (
            cos_latitude * torch.sin(longitude_grid),
            torch.sin(latitude_grid),
            -cos_latitude * torch.cos(longitude_grid),
        ),
        dim=-1,
    )
    return ((direction + 1.0) * 0.5).unsqueeze(0)


class CubemapProjectionTests(unittest.TestCase):
    def test_node_is_registered(self):
        self.assertIs(package.NODE_CLASS_MAPPINGS["EquirectangularToCubemapStrip"], CubemapStrip)
        self.assertEqual(
            package.NODE_DISPLAY_NAME_MAPPINGS["EquirectangularToCubemapStrip"],
            "Pepe Equirectangular to Cubemap Strip",
        )

    def test_auto_face_size_is_quarter_of_panorama_width(self):
        panorama = torch.zeros((2, 96, 320, 3), dtype=torch.float32)

        strip = CubemapStrip.convert(panorama, face_size=0)[0]

        self.assertEqual(strip.shape, (2, 80, 320, 3))
        self.assertEqual(strip.dtype, panorama.dtype)

    def test_auto_size_preserves_strip_width_and_vertical_coverage(self):
        panorama = torch.zeros((1, 96, 320, 3), dtype=torch.float32)

        strip = CubemapStrip.convert(panorama, side_count=8)[0]

        expected_height = round((320 // 8) / math.tan(math.pi / 8))
        self.assertEqual(strip.shape, (1, expected_height, 320, 3))

    def test_side_count_is_exposed_with_cubemap_default(self):
        inputs = CubemapStrip.INPUT_TYPES()["required"]
        side_count = inputs["side_count"]

        self.assertEqual(side_count[1]["default"], 4)
        self.assertEqual(side_count[1]["min"], 2)
        self.assertEqual(inputs["vertical_fov"][1]["default"], 90.0)

    def test_two_sides_are_accepted(self):
        panorama = torch.zeros((1, 32, 64, 3), dtype=torch.float32)

        strip = CubemapStrip.convert(panorama, side_count=2)[0]

        self.assertEqual(strip.shape[0], 1)
        self.assertEqual(strip.shape[2], 64)

    def test_faces_are_front_right_back_left(self):
        size = 65
        strip = CubemapStrip.convert(directional_panorama(), face_size=size)[0][0]
        centers = torch.stack(
            [strip[size // 2, face * size + size // 2] for face in range(4)]
        )
        expected = torch.tensor(
            [
                [1.0, 0.5, 0.25],
                [0.5, 1.0, 0.25],
                [0.0, 0.5, 0.25],
                [0.5, 0.0, 0.25],
            ]
        )

        self.assertTrue(torch.allclose(centers, expected, atol=0.025), (centers, expected))

    def test_face_boundaries_and_outer_edges_are_continuous(self):
        size = 64
        strip = CubemapStrip.convert(directional_panorama(), face_size=size)[0][0]

        for boundary in (size, size * 2, size * 3):
            self.assertLess((strip[:, boundary - 1] - strip[:, boundary]).abs().max().item(), 0.03)
        self.assertLess((strip[:, -1] - strip[:, 0]).abs().max().item(), 0.03)

    def test_each_face_uses_square_ninety_degree_pinhole_projection(self):
        size = 65
        row = 16
        column = 48
        local_x = ((column + 0.5) / size) * 2.0 - 1.0
        local_y = 1.0 - ((row + 0.5) / size) * 2.0
        strip = CubemapStrip.convert(cartesian_direction_panorama(), face_size=size)[0][0]
        raw_directions = (
            torch.tensor([local_x, local_y, -1.0]),
            torch.tensor([1.0, local_y, local_x]),
            torch.tensor([-local_x, local_y, 1.0]),
            torch.tensor([-1.0, local_y, -local_x]),
        )
        expected = torch.stack(
            [((direction / torch.linalg.vector_norm(direction)) + 1.0) * 0.5 for direction in raw_directions]
        )
        actual = torch.stack(
            [strip[row, face * size + column] for face in range(4)]
        )

        self.assertTrue(torch.allclose(actual, expected, atol=0.012), (actual, expected))

    def test_eight_sides_use_forty_five_by_ninety_degree_pinhole_projection(self):
        side_count = 8
        size = 65
        height = round(size / math.tan(math.pi / side_count))
        row = 39
        column = 48
        local_x = (((column + 0.5) / size) * 2.0 - 1.0) * math.tan(math.pi / side_count)
        local_y = 1.0 - ((row + 0.5) / height) * 2.0
        strip = CubemapStrip.convert(
            cartesian_direction_panorama(),
            face_size=size,
            side_count=side_count,
        )[0][0]

        expected = []
        for face_index in range(side_count):
            yaw = face_index * 2.0 * math.pi / side_count
            direction = torch.tensor(
                [
                    math.sin(yaw) + local_x * math.cos(yaw),
                    local_y,
                    -math.cos(yaw) + local_x * math.sin(yaw),
                ]
            )
            expected.append(((direction / torch.linalg.vector_norm(direction)) + 1.0) * 0.5)
        actual = torch.stack(
            [strip[row, face * size + column] for face in range(side_count)]
        )

        self.assertEqual(strip.shape, (height, side_count * size, 3))
        self.assertTrue(torch.allclose(actual, torch.stack(expected), atol=0.012))

    def test_custom_vertical_fov_controls_coverage_and_height(self):
        side_count = 8
        size = 64
        vertical_fov = 60.0
        vertical_scale = math.tan(math.radians(vertical_fov) / 2.0)
        expected_height = round(size * vertical_scale / math.tan(math.pi / side_count))

        strip = CubemapStrip.convert(
            cartesian_direction_panorama(),
            face_size=size,
            side_count=side_count,
            vertical_fov=vertical_fov,
        )[0]

        self.assertEqual(strip.shape, (1, expected_height, side_count * size, 3))

    def test_configurable_side_boundaries_and_outer_edges_are_continuous(self):
        side_count = 16
        size = 32
        strip = CubemapStrip.convert(
            directional_panorama(),
            face_size=size,
            side_count=side_count,
        )[0][0]

        for boundary in range(size, side_count * size, size):
            self.assertLess((strip[:, boundary - 1] - strip[:, boundary]).abs().max().item(), 0.02)
        self.assertLess((strip[:, -1] - strip[:, 0]).abs().max().item(), 0.02)


class CylindricalProjectionTests(unittest.TestCase):
    def test_node_is_registered(self):
        self.assertIs(package.NODE_CLASS_MAPPINGS["EquirectangularToCylindrical"], Cylindrical)
        self.assertEqual(
            package.NODE_DISPLAY_NAME_MAPPINGS["EquirectangularToCylindrical"],
            "Pepe Equirectangular to Cylindrical",
        )
        inputs = Cylindrical.INPUT_TYPES()["required"]
        self.assertAlmostEqual(
            inputs["max_latitude"][1]["default"],
            Cylindrical.DEFAULT_MAX_LATITUDE,
        )

    def test_default_coverage_preserves_two_to_one_dimensions(self):
        panorama = torch.zeros((2, 160, 320, 3), dtype=torch.float32)

        cylindrical = Cylindrical.convert(panorama)[0]

        self.assertEqual(cylindrical.shape, (2, 160, 320, 3))
        self.assertEqual(cylindrical.dtype, panorama.dtype)

    def test_explicit_dimensions_override_square_surface_pixel_sizing(self):
        panorama = torch.zeros((1, 64, 128, 3), dtype=torch.float32)

        cylindrical = Cylindrical.convert(
            panorama,
            output_width=96,
            output_height=40,
            max_latitude=70.0,
        )[0]

        self.assertEqual(cylindrical.shape, (1, 40, 96, 3))

    def test_pixels_follow_constant_radius_cylinder_directions(self):
        width = 257
        height = 129
        row = 23
        column = 181
        latitude_limit = 65.0
        half_height = math.tan(math.radians(latitude_limit))
        longitude = ((column + 0.5) / width) * (2.0 * math.pi) - math.pi
        cylinder_y = half_height * (1.0 - 2.0 * (row + 0.5) / height)
        expected_direction = torch.tensor(
            [math.sin(longitude), cylinder_y, -math.cos(longitude)]
        )
        expected = ((expected_direction / torch.linalg.vector_norm(expected_direction)) + 1.0) * 0.5

        cylindrical = Cylindrical.convert(
            cartesian_direction_panorama(),
            output_width=width,
            output_height=height,
            max_latitude=latitude_limit,
        )[0][0]

        self.assertTrue(torch.allclose(cylindrical[row, column], expected, atol=0.012))

    def test_left_and_right_edges_are_continuous(self):
        cylindrical = Cylindrical.convert(
            cartesian_direction_panorama(),
            output_width=256,
            output_height=128,
        )[0][0]

        self.assertLess((cylindrical[:, -1] - cylindrical[:, 0]).abs().max().item(), 0.02)


if __name__ == "__main__":
    unittest.main()
