"""Interactive image selection node.

Derived from cg-image-filter by Chris Goringe, licensed under Apache-2.0.
"""

import random

import torch
from comfy.model_management import InterruptProcessingException
from nodes import PreviewImage

from .pepe_image_filter_messaging import Response, TimeoutResponse, send_and_wait


class PepeImageFilter(PreviewImage):
    MAX_CHOICES = 8
    RETURN_TYPES = (
        "IMAGE",
        "LATENT",
        "MASK",
        "STRING",
        "STRING",
        "STRING",
        "STRING",
        "INT",
        "STRING",
    )
    RETURN_NAMES = (
        "images",
        "latents",
        "masks",
        "extra1",
        "extra2",
        "extra3",
        "indexes",
        "choice_index",
        "choice_name",
    )
    FUNCTION = "filter_images"
    CATEGORY = "PepeUtils/image"
    DESCRIPTION = "Pauses the workflow so you can choose which images continue."

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "timeout": (
                    "INT",
                    {"default": 600, "min": 1, "max": 1_000_000, "tooltip": "Timeout in seconds"},
                ),
                "ontimeout": (["send none", "send all", "send first", "send last"],),
            },
            "optional": {
                "latents": ("LATENT", {"tooltip": "Pass through matching latent samples"}),
                "masks": ("MASK", {"tooltip": "Pass through matching masks"}),
                "tip": ("STRING", {"default": ""}),
                "extra1": ("STRING", {"default": ""}),
                "extra2": ("STRING", {"default": ""}),
                "extra3": ("STRING", {"default": ""}),
                "choices": (
                    "STRING",
                    {
                        "default": "Proceed",
                        "multiline": True,
                        "tooltip": "One flow-control choice per line (maximum 8)",
                    },
                ),
                "default_choice": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": cls.MAX_CHOICES - 1,
                        "tooltip": "Zero-based choice used for timeout and automatic sends",
                    },
                ),
                "pick_list_start": (
                    "INT",
                    {"default": 0, "tooltip": "Index assigned to the first image"},
                ),
                "pick_list": (
                    "STRING",
                    {"default": "", "tooltip": "Comma-separated indices to select automatically"},
                ),
                "video_frames": (
                    "INT",
                    {"default": 1, "min": 1, "tooltip": "Treat each block of N images as a video"},
                ),
                "equirectangular_projection": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": "Open still-image candidates in an interactive panorama projection",
                    },
                ),
                "audiofile": (
                    "STRING",
                    {"default": "", "tooltip": "Audio path, URL, or bundled audio filename"},
                ),
                "graph_id": ("STRING", {"default": ""}),
            },
            "hidden": {"unique_id": "UNIQUE_ID"},
        }

    @staticmethod
    def parse_pick_list(pick_list: str, batch_size: int) -> list[int]:
        return [int(value.strip()) % batch_size for value in pick_list.split(",")] if pick_list else []

    @classmethod
    def parse_choices(cls, choices: str) -> list[str]:
        parsed = [line.strip() for line in (choices or "").splitlines() if line.strip()]
        if len(parsed) > cls.MAX_CHOICES:
            raise ValueError(f"Pepe Image Filter supports at most {cls.MAX_CHOICES} choices")
        return parsed

    @staticmethod
    def _default_choice_index(choice_names: list[str], default_choice: int) -> int:
        if not choice_names:
            return 0
        return min(max(int(default_choice), 0), len(choice_names) - 1)

    @classmethod
    def IS_CHANGED(cls, pick_list="", **kwargs):
        try:
            parsed = [int(value.strip()) for value in pick_list.split(",")] if pick_list else []
            if parsed:
                return ",".join(str(value) for value in parsed)
        except (TypeError, ValueError):
            pass
        return random.random()

    @staticmethod
    def _select_tensor(tensor, indices):
        if tensor is None:
            return None
        try:
            return torch.stack([tensor[index] for index in indices])
        except IndexError:
            print(f"Pepe Image Filter could not select indices {indices} from shape {tensor.shape}")
            return None

    @classmethod
    def filter_images(
        cls,
        images,
        timeout,
        ontimeout,
        latents=None,
        masks=None,
        tip="",
        extra1="",
        extra2="",
        extra3="",
        choices="",
        default_choice=0,
        pick_list_start=0,
        pick_list="",
        video_frames=1,
        equirectangular_projection=False,
        audiofile="",
        graph_id="",
        unique_id=None,
        **kwargs,
    ):
        if images is None:
            raise ValueError("Pepe Image Filter received no images")

        batch_size = images.shape[0]
        if batch_size == 0:
            raise InterruptProcessingException()
        if video_frames > batch_size:
            video_frames = 1

        try:
            selected = cls.parse_pick_list(pick_list, batch_size)
        except (TypeError, ValueError) as error:
            print(f"{error} parsing Pepe Image Filter pick_list; opening manual selection")
            selected = []

        returned_extras = (extra1, extra2, extra3)
        choice_names = cls.parse_choices(choices)
        selected_choice = cls._default_choice_index(choice_names, default_choice)
        if not selected:
            all_same = all(torch.equal(images[index], images[0]) for index in range(1, batch_size))
            urls = cls().save_images(images=images, **kwargs)["ui"]["images"]
            payload = {
                "urls": urls,
                "allsame": all_same,
                "extras": [extra1, extra2, extra3],
                "choices": choice_names,
                "default_choice": selected_choice,
                "tip": tip,
                "video_frames": video_frames,
                "equirectangular_projection": bool(equirectangular_projection),
                "audiopath": audiofile,
            }
            response: Response = send_and_wait(payload, timeout, graph_id, node_id=unique_id)

            if isinstance(response, TimeoutResponse):
                timeout_selections = {
                    "send none": [],
                    "send all": list(range(batch_size // video_frames)),
                    "send first": [0],
                    "send last": [(batch_size // video_frames) - 1],
                }
                selected = timeout_selections[ontimeout]
            else:
                returned_extras = response.get_extras(returned_extras)
                selected = response.selection
                if response.choice_index is not None:
                    if not 0 <= response.choice_index < len(choice_names):
                        raise ValueError(
                            f"Pepe Image Filter received invalid choice index {response.choice_index}"
                        )
                    selected_choice = response.choice_index

        if not selected:
            raise InterruptProcessingException()

        if video_frames > 1:
            selected = [
                video_index * video_frames + frame
                for video_index in selected
                for frame in range(video_frames)
            ]

        selected_images = cls._select_tensor(images, selected)
        selected_masks = cls._select_tensor(masks, selected)
        selected_latents = None
        if latents is not None:
            latent_samples = cls._select_tensor(latents["samples"], selected)
            selected_latents = {**latents, "samples": latent_samples} if latent_samples is not None else None

        indexes = ",".join(str(index + int(pick_list_start)) for index in selected)
        choice_name = choice_names[selected_choice] if choice_names else ""
        return (
            selected_images,
            selected_latents,
            selected_masks,
            *returned_extras,
            indexes,
            selected_choice,
            choice_name,
        )
