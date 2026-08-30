import importlib.util
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
COMFY_ROOT = ROOT.parents[1]
if str(COMFY_ROOT) not in sys.path:
    sys.path.insert(0, str(COMFY_ROOT))

from comfy_execution.graph_utils import ExecutionBlocker

PACKAGE_NAME = "pepeutils_break_test"
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
PepeBreak = package.NODE_CLASS_MAPPINGS["PepeBreak"]


class PepeBreakTests(unittest.TestCase):
    def test_node_is_registered(self):
        self.assertIs(package.NODE_CLASS_MAPPINGS["PepeBreak"], PepeBreak)
        self.assertEqual(package.NODE_DISPLAY_NAME_MAPPINGS["PepeBreak"], "Pepe Break")

    def test_input_is_lazy_and_toggle_is_labeled(self):
        inputs = PepeBreak.INPUT_TYPES()["required"]

        self.assertTrue(inputs["value"][1]["lazy"])
        self.assertTrue(inputs["enabled"][1]["default"])
        self.assertEqual(inputs["enabled"][1]["label_on"], "CONTINUE")
        self.assertEqual(inputs["enabled"][1]["label_off"], "BREAK")

    def test_continue_requests_and_passes_lazy_value(self):
        marker = object()

        self.assertEqual(PepeBreak.check_lazy_status(enabled=True), ["value"])
        self.assertEqual(PepeBreak.check_lazy_status(value=marker, enabled=True), [])
        self.assertIs(PepeBreak.control_flow(value=marker, enabled=True)[0], marker)

    def test_break_does_not_request_value_and_blocks_branch(self):
        self.assertEqual(PepeBreak.check_lazy_status(enabled=False), [])

        output = PepeBreak.control_flow(enabled=False)[0]

        self.assertIsInstance(output, ExecutionBlocker)
        self.assertIsNone(output.message)


if __name__ == "__main__":
    unittest.main()
