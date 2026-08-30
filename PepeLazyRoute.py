"""Lazy multi-way flow routing for ComfyUI workflows."""

from comfy_execution.graph_utils import ExecutionBlocker


class PepeLazyRoute:
    MAX_CHOICES = 8

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "choice_index": (
                    "INT",
                    {
                        "default": 0,
                        "forceInput": True,
                        "min": 0,
                        "max": cls.MAX_CHOICES - 1,
                        "tooltip": "Zero-based choice index from Pepe Image Filter",
                    },
                ),
            },
            "optional": {
                f"choice_{index}": ("*", {"lazy": True})
                for index in range(cls.MAX_CHOICES)
            },
        }

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("output",)
    FUNCTION = "select"
    CATEGORY = "PepeUtils/flow"
    DESCRIPTION = "Evaluates and returns only the branch selected by a Pepe Image Filter choice."

    @classmethod
    def _choice_key(cls, choice_index):
        index = int(choice_index)
        if not 0 <= index < cls.MAX_CHOICES:
            raise ValueError(f"Pepe Lazy Route choice index must be between 0 and {cls.MAX_CHOICES - 1}")
        return f"choice_{index}"

    @classmethod
    def check_lazy_status(cls, choice_index, **kwargs):
        key = cls._choice_key(choice_index)
        if kwargs.get(key) is None:
            return [key]
        return []

    @classmethod
    def select(cls, choice_index, **kwargs):
        key = cls._choice_key(choice_index)
        if key not in kwargs:
            raise ValueError(f"Pepe Lazy Route input {key} is not connected")
        return (kwargs[key],)


class PepeRouteSplit:
    """Block every route except the selected one, including independent output paths."""

    MAX_CHOICES = 8

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input": ("*",),
                "choice_index": (
                    "INT",
                    {
                        "default": 0,
                        "forceInput": True,
                        "min": 0,
                        "max": cls.MAX_CHOICES - 1,
                        "tooltip": "Zero-based choice index from Pepe Image Filter",
                    },
                ),
            },
        }

    RETURN_TYPES = ("*",) * MAX_CHOICES
    RETURN_NAMES = tuple(f"choice_{index}" for index in range(MAX_CHOICES))
    FUNCTION = "split"
    CATEGORY = "PepeUtils/flow"
    DESCRIPTION = (
        "Passes the input through the selected output and silently blocks every other route, "
        "including routes ending in their own Save or Preview node."
    )

    @classmethod
    def split(cls, input, choice_index):
        index = int(choice_index)
        if not 0 <= index < cls.MAX_CHOICES:
            raise ValueError(f"Pepe Route Split choice index must be between 0 and {cls.MAX_CHOICES - 1}")
        return tuple(input if route == index else ExecutionBlocker(None) for route in range(cls.MAX_CHOICES))
