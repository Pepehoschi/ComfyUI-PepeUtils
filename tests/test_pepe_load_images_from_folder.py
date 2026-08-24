import importlib.util
import pathlib
import sys
import tempfile
import unittest

import torch
from PIL import Image


ROOT = pathlib.Path(__file__).resolve().parents[1]
COMFY_ROOT = ROOT.parents[1]
if str(COMFY_ROOT) not in sys.path:
    sys.path.insert(0, str(COMFY_ROOT))

PACKAGE_NAME = "pepeutils_folder_loader_test"
if PACKAGE_NAME not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE_NAME] = package
    spec.loader.exec_module(package)

module = sys.modules[f"{PACKAGE_NAME}.PepeLoadImagesFromFolder"]
PepeLoadImagesFromFolder = module.PepeLoadImagesFromFolder


class PepeLoadImagesFromFolderTests(unittest.TestCase):
    def test_node_is_registered_as_list_output(self):
        package = sys.modules[PACKAGE_NAME]
        self.assertIs(package.NODE_CLASS_MAPPINGS["PepeLoadImagesFromFolder"], PepeLoadImagesFromFolder)
        self.assertEqual(
            package.NODE_DISPLAY_NAME_MAPPINGS["PepeLoadImagesFromFolder"],
            "Pepe Load Images From Folder",
        )
        self.assertEqual(PepeLoadImagesFromFolder.OUTPUT_IS_LIST, (True, True, True, False))

    def test_rejects_an_empty_folder_value(self):
        self.assertEqual(
            PepeLoadImagesFromFolder.VALIDATE_INPUTS(""),
            "Image folder is required.",
        )

    def test_loads_absolute_folder_in_filename_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            Image.new("RGB", (3, 2), (255, 0, 0)).save(root / "b.png")
            Image.new("RGB", (2, 3), (0, 255, 0)).save(root / "A.jpg")
            (root / "ignored.txt").write_text("not an image", encoding="utf-8")

            images, masks, filenames, count = PepeLoadImagesFromFolder().load_images(directory)

        self.assertEqual(filenames, ["A.jpg", "b.png"])
        self.assertEqual(count, 2)
        self.assertEqual(tuple(images[0].shape), (1, 3, 2, 3))
        self.assertEqual(tuple(masks[0].shape), (1, 3, 2))
        self.assertEqual(float(masks[0].max()), 0.0)

    def test_preserves_alpha_as_inverted_mask(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "alpha.png"
            source = Image.new("RGBA", (2, 1), (255, 0, 0, 255))
            source.putpixel((1, 0), (255, 0, 0, 0))
            source.save(path)

            _, masks, _, _ = PepeLoadImagesFromFolder().load_images(directory)

        self.assertTrue(torch.equal(masks[0], torch.tensor([[[0.0, 1.0]]])))

    def test_applies_stride_then_load_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for index in range(5):
                Image.new("RGB", (1, 1), (index, 0, 0)).save(root / f"{index}.png")

            _, _, filenames, count = PepeLoadImagesFromFolder().load_images(
                directory,
                image_load_cap=2,
                select_every_nth=2,
            )

        self.assertEqual(filenames, ["0.png", "2.png"])
        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
