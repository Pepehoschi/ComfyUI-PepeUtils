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

from comfy_execution.graph_utils import ExecutionBlocker

if "pepeutils_test" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "pepeutils_test",
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package
    spec.loader.exec_module(package)

package = sys.modules["pepeutils_test"]
filter_module = sys.modules["pepeutils_test.PepeImageFilter"]
PepeImageFilter = package.NODE_CLASS_MAPPINGS["PepeImageFilter"]
PepeLazyRoute = package.NODE_CLASS_MAPPINGS["PepeLazyRoute"]
PepeRouteSplit = package.NODE_CLASS_MAPPINGS["PepeRouteSplit"]


class PepeImageFilterTests(unittest.TestCase):
    def test_node_is_registered_with_requested_name(self):
        self.assertIs(package.NODE_CLASS_MAPPINGS["PepeImageFilter"], PepeImageFilter)
        self.assertEqual(package.NODE_DISPLAY_NAME_MAPPINGS["PepeImageFilter"], "Pepe Image Filter")
        self.assertIs(package.NODE_CLASS_MAPPINGS["PepeLazyRoute"], PepeLazyRoute)
        self.assertEqual(package.NODE_DISPLAY_NAME_MAPPINGS["PepeLazyRoute"], "Pepe Lazy Route")
        self.assertIs(package.NODE_CLASS_MAPPINGS["PepeRouteSplit"], PepeRouteSplit)
        self.assertEqual(package.NODE_DISPLAY_NAME_MAPPINGS["PepeRouteSplit"], "Pepe Route Split")

    def test_pick_list_selects_matching_images_latents_and_masks(self):
        images = torch.arange(4 * 2 * 2 * 3).reshape(4, 2, 2, 3)
        masks = torch.arange(4 * 2 * 2).reshape(4, 2, 2)
        latents = {"samples": torch.arange(4 * 2).reshape(4, 2), "batch_index": [10, 11, 12, 13]}

        result = PepeImageFilter.filter_images(
            images,
            timeout=10,
            ontimeout="send none",
            masks=masks,
            latents=latents,
            extra1="one",
            extra2="two",
            extra3="three",
            pick_list="3, 1",
            pick_list_start=1,
        )

        self.assertTrue(torch.equal(result[0], images[[3, 1]]))
        self.assertTrue(torch.equal(result[1]["samples"], latents["samples"][[3, 1]]))
        self.assertEqual(result[1]["batch_index"], latents["batch_index"])
        self.assertTrue(torch.equal(result[2], masks[[3, 1]]))
        self.assertEqual(result[3:], ("one", "two", "three", "4,2", 0, ""))

    def test_video_selection_expands_to_all_frames(self):
        images = torch.arange(6).reshape(6, 1, 1, 1)

        result = PepeImageFilter.filter_images(
            images,
            timeout=10,
            ontimeout="send none",
            pick_list="1",
            video_frames=2,
        )

        self.assertTrue(torch.equal(result[0], images[[2, 3]]))
        self.assertEqual(result[6], "2,3")

    def test_pick_list_uses_clamped_default_choice(self):
        images = torch.zeros((1, 1, 1, 3))

        result = PepeImageFilter.filter_images(
            images,
            timeout=10,
            ontimeout="send none",
            pick_list="0",
            choices="Keep\nResample",
            default_choice=7,
        )

        self.assertEqual(result[-2:], (1, "Resample"))

    def test_choices_are_trimmed_and_limited(self):
        choices_input = PepeImageFilter.INPUT_TYPES()["optional"]["choices"]
        self.assertEqual(choices_input[1]["default"], "Proceed")
        self.assertEqual(PepeImageFilter.parse_choices(" Keep \n\n Resample\r\n"), ["Keep", "Resample"])
        with self.assertRaisesRegex(ValueError, "at most 8"):
            PepeImageFilter.parse_choices("\n".join(str(index) for index in range(9)))

    def test_pick_list_wraps_indices_to_batch(self):
        self.assertEqual(PepeImageFilter.parse_pick_list("4, -1", 4), [0, 3])

    def test_projection_input_defaults_to_false(self):
        projection = PepeImageFilter.INPUT_TYPES()["optional"]["equirectangular_projection"]
        self.assertEqual(projection[0], "BOOLEAN")
        self.assertFalse(projection[1]["default"])

    def test_projection_flag_is_sent_to_popup(self):
        images = torch.zeros((2, 2, 4, 3))
        response = filter_module.Response(selection=["0"])

        with mock.patch.object(PepeImageFilter, "save_images") as save_images:
            save_images.return_value = {
                "ui": {
                    "images": [
                        {"filename": "0.png", "type": "temp", "subfolder": ""},
                        {"filename": "1.png", "type": "temp", "subfolder": ""},
                    ]
                }
            }
            with mock.patch.object(
                filter_module,
                "send_and_wait",
                return_value=response,
            ) as send_and_wait:
                PepeImageFilter.filter_images(
                    images,
                    timeout=10,
                    ontimeout="send none",
                    equirectangular_projection=True,
                )

        payload = send_and_wait.call_args.args[0]
        self.assertTrue(payload["equirectangular_projection"])

    def test_popup_message_targets_the_executing_node(self):
        images = torch.zeros((1, 2, 4, 3))
        response = filter_module.Response(selection=["0"])

        with mock.patch.object(PepeImageFilter, "save_images") as save_images:
            save_images.return_value = {
                "ui": {"images": [{"filename": "0.png", "type": "temp", "subfolder": ""}]}
            }
            with mock.patch.object(filter_module, "send_and_wait", return_value=response) as send_and_wait:
                PepeImageFilter.filter_images(
                    images,
                    timeout=10,
                    ontimeout="send none",
                    graph_id="graph-a",
                    unique_id="node-42",
                )

        self.assertEqual(send_and_wait.call_args.kwargs["node_id"], "node-42")
        self.assertEqual(send_and_wait.call_args.args[2], "graph-a")

    def test_popup_choice_is_returned_with_its_label(self):
        images = torch.zeros((1, 2, 4, 3))
        response = filter_module.Response(selection=["0"], choice_index=1)

        with mock.patch.object(PepeImageFilter, "save_images") as save_images:
            save_images.return_value = {
                "ui": {"images": [{"filename": "0.png", "type": "temp", "subfolder": ""}]}
            }
            with mock.patch.object(filter_module, "send_and_wait", return_value=response) as send_and_wait:
                result = PepeImageFilter.filter_images(
                    images,
                    timeout=10,
                    ontimeout="send none",
                    choices="Keep\nResample",
                )

        payload = send_and_wait.call_args.args[0]
        self.assertEqual(payload["choices"], ["Keep", "Resample"])
        self.assertEqual(payload["default_choice"], 0)
        self.assertEqual(result[-2:], (1, "Resample"))

    def test_popup_rejects_an_invalid_choice(self):
        images = torch.zeros((1, 2, 4, 3))
        response = filter_module.Response(selection=["0"], choice_index=2)

        with mock.patch.object(PepeImageFilter, "save_images") as save_images:
            save_images.return_value = {
                "ui": {"images": [{"filename": "0.png", "type": "temp", "subfolder": ""}]}
            }
            with mock.patch.object(filter_module, "send_and_wait", return_value=response):
                with self.assertRaisesRegex(ValueError, "invalid choice index 2"):
                    PepeImageFilter.filter_images(
                        images,
                        timeout=10,
                        ontimeout="send none",
                        choices="Keep\nResample",
                    )

    def test_lazy_route_requests_and_returns_only_selected_input(self):
        marker = object()

        self.assertEqual(PepeLazyRoute.check_lazy_status(2, choice_0=object()), ["choice_2"])
        self.assertEqual(PepeLazyRoute.check_lazy_status(2, choice_2=marker), [])
        self.assertIs(PepeLazyRoute.select(2, choice_2=marker)[0], marker)
        with self.assertRaisesRegex(ValueError, "choice_2 is not connected"):
            PepeLazyRoute.select(2, choice_1=marker)

    def test_route_split_blocks_every_unselected_terminal_path(self):
        marker = object()

        outputs = PepeRouteSplit.split(marker, 2)

        self.assertEqual(len(outputs), 8)
        self.assertIs(outputs[2], marker)
        self.assertTrue(
            all(
                isinstance(output, ExecutionBlocker) and output.message is None
                for index, output in enumerate(outputs)
                if index != 2
            )
        )

    def test_route_split_rejects_out_of_range_choice(self):
        with self.assertRaisesRegex(ValueError, "between 0 and 7"):
            PepeRouteSplit.split(object(), 8)

    def test_projected_state_sends_the_current_selection(self):
        popup_source = (ROOT / "web" / "pepe_image_filter" / "popup.js").read_text(encoding="utf-8")

        self.assertIn(
            "this.state==State.FILTER || this.state==State.ZOOMED || this.state==State.PROJECTED",
            popup_source,
        )
        self.assertIn("this._send_response({choice_index:choice_index})", popup_source)
        self.assertIn("const uid = detail.node_id || app.runningNodeId", popup_source)
        self.assertIn("msg.request_id = this.active_request_id", popup_source)


if __name__ == "__main__":
    unittest.main()
