import contextlib
import importlib.util
import io
import math
import pathlib
import sys
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
COMFY_ROOT = ROOT.parents[1]
if str(COMFY_ROOT) not in sys.path:
    sys.path.insert(0, str(COMFY_ROOT))

PACKAGE_NAME = "pepeutils_console_print_test"
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
PepeConsolePrint = package.NODE_CLASS_MAPPINGS["PepeConsolePrint"]
console_print_module = sys.modules[f"{PACKAGE_NAME}.PepeConsolePrint"]


class PepeConsolePrintTests(unittest.TestCase):
    def test_node_is_registered(self):
        self.assertIs(package.NODE_CLASS_MAPPINGS["PepeConsolePrint"], PepeConsolePrint)
        self.assertEqual(
            package.NODE_DISPLAY_NAME_MAPPINGS["PepeConsolePrint"],
            "Pepe Console Print",
        )

    def test_contract_accepts_and_returns_any_type(self):
        inputs = PepeConsolePrint.INPUT_TYPES()["required"]

        self.assertEqual(inputs["value"][0], "*")
        self.assertEqual(inputs["message"][0], "STRING")
        self.assertTrue(inputs["message"][1]["multiline"])
        self.assertEqual(inputs["color"][1]["default"], "Default")
        self.assertIn("Yellow", inputs["color"][0])
        self.assertIn("Bright Yellow", inputs["color"][0])
        self.assertEqual(PepeConsolePrint.RETURN_TYPES, ("*",))

    def test_prints_message_and_preserves_value_identity(self):
        marker = object()
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            result = PepeConsolePrint.print_message(marker, "workflow reached checkpoint")

        self.assertIs(result[0], marker)
        self.assertEqual(output.getvalue(), "workflow reached checkpoint\n")

    def test_prints_selected_color_and_resets_terminal(self):
        with mock.patch.object(console_print_module.logging, "info") as log_info:
            PepeConsolePrint.print_message(None, "Lowres Sampling started.", "Bright Yellow")

        log_info.assert_called_once_with(
            "\033[1mLowres Sampling started.\033[22m",
            extra={"color": "yellow"},
        )

    def test_standard_color_uses_comfyui_logger_color_metadata(self):
        with mock.patch.object(console_print_module.logging, "info") as log_info:
            PepeConsolePrint.print_message(None, "checkpoint", "Cyan")

        log_info.assert_called_once_with("checkpoint", extra={"color": "cyan"})

    def test_enables_ansi_for_both_windows_console_streams(self):
        class FakeKernel32:
            def __init__(self):
                self.requested_streams = []
                self.updated_modes = []

            def GetStdHandle(self, stream_id):
                self.requested_streams.append(stream_id)
                return stream_id

            @staticmethod
            def GetConsoleMode(handle, mode_pointer):
                mode_pointer._obj.value = 0x0001
                return True

            def SetConsoleMode(self, handle, mode):
                self.updated_modes.append((handle, mode))
                return True

        kernel32 = FakeKernel32()

        enabled = console_print_module._enable_windows_ansi(
            kernel32=kernel32,
            os_name="nt",
        )

        self.assertTrue(enabled)
        self.assertEqual(kernel32.requested_streams, [-11, -12])
        self.assertEqual(kernel32.updated_modes, [(-11, 0x0005), (-12, 0x0005)])

    def test_is_changed_disables_execution_cache(self):
        self.assertTrue(
            math.isnan(PepeConsolePrint.IS_CHANGED(object(), "message", "Yellow"))
        )


if __name__ == "__main__":
    unittest.main()
