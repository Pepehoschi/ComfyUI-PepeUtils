"""Console logging passthrough for ComfyUI workflows."""

import ctypes
import logging
import os


def _enable_windows_ansi(kernel32=None, os_name=None):
    """Enable ANSI escape processing for the Windows console output streams."""
    if (os_name or os.name) != "nt":
        return True

    try:
        kernel32 = kernel32 or ctypes.windll.kernel32
        enabled = False
        for stream_id in (-11, -12):  # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
            handle = kernel32.GetStdHandle(stream_id)
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                enabled = bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004)) or enabled
        return enabled
    except (AttributeError, OSError):
        return False


class PepeConsolePrint:
    COLOR_CODES = {
        "Default": None,
        "Red": 31,
        "Green": 32,
        "Yellow": 33,
        "Blue": 34,
        "Magenta": 35,
        "Cyan": 36,
        "White": 37,
        "Bright Red": 91,
        "Bright Green": 92,
        "Bright Yellow": 93,
        "Bright Blue": 94,
        "Bright Magenta": 95,
        "Bright Cyan": 96,
        "Bright White": 97,
    }
    LOGGER_COLORS = {
        "Red": "red",
        "Green": "green",
        "Yellow": "yellow",
        "Blue": "blue",
        "Magenta": "magenta",
        "Cyan": "cyan",
        "White": "white",
    }

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (
                    "*",
                    {
                        "tooltip": "Any value to pass through unchanged",
                    },
                ),
                "message": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Text printed to the ComfyUI server console when this node runs",
                    },
                ),
                "color": (
                    list(cls.COLOR_CODES),
                    {
                        "default": "Default",
                        "tooltip": "ANSI color used for the console message",
                    },
                ),
            },
        }

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("value",)
    FUNCTION = "print_message"
    CATEGORY = "PepeUtils/utils"
    DESCRIPTION = (
        "Prints the message to the ComfyUI server console and passes any input value "
        "through unchanged."
    )

    @staticmethod
    def IS_CHANGED(value, message, color="Default"):
        """Run for every queued workflow instead of reusing a cached result."""
        return float("nan")

    @classmethod
    def print_message(cls, value, message, color="Default"):
        color_code = cls.COLOR_CODES.get(color)
        if color_code is None:
            print(message, flush=True)
        else:
            _enable_windows_ansi()
            base_color = color.removeprefix("Bright ")
            formatted_message = (
                f"\033[1m{message}\033[22m"
                if color.startswith("Bright ")
                else message
            )
            logging.info(
                formatted_message,
                extra={"color": cls.LOGGER_COLORS[base_color]},
            )
        return (value,)


NODE_CLASS_MAPPINGS = {"PepeConsolePrint": PepeConsolePrint}
NODE_DISPLAY_NAME_MAPPINGS = {"PepeConsolePrint": "Pepe Console Print"}
