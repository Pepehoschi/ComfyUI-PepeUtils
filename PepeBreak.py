"""Toggleable lazy branch blocker for ComfyUI workflows."""

from comfy_execution.graph_utils import ExecutionBlocker


class PepeBreak:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "value": (
                    "*",
                    {
                        "lazy": True,
                        "tooltip": "Any value to pass through while the break is disabled",
                    },
                ),
                "enabled": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "CONTINUE",
                        "label_off": "BREAK",
                        "tooltip": "Continue passes the value; Break blocks this downstream branch",
                    },
                ),
            },
        }

    RETURN_TYPES = ("*",)
    RETURN_NAMES = ("value",)
    FUNCTION = "control_flow"
    CATEGORY = "PepeUtils/flow"
    DESCRIPTION = (
        "Passes any value through when set to Continue and silently blocks the downstream "
        "branch when set to Break. A blocked branch does not evaluate this node's lazy input."
    )

    @staticmethod
    def check_lazy_status(value=None, enabled=True):
        if bool(enabled) and value is None:
            return ["value"]
        return []

    @staticmethod
    def control_flow(value=None, enabled=True):
        if not bool(enabled):
            return (ExecutionBlocker(None),)
        return (value,)


NODE_CLASS_MAPPINGS = {"PepeBreak": PepeBreak}
NODE_DISPLAY_NAME_MAPPINGS = {"PepeBreak": "Pepe Break"}
