"""Namespaced browser messaging for Pepe Image Filter.

Derived from cg-image-filter by Chris Goringe, licensed under Apache-2.0.
"""

import json
import time
from typing import Optional

from aiohttp import web
from comfy.model_management import InterruptProcessingException
from comfy.model_management import throw_exception_if_processing_interrupted
from server import PromptServer


REQUEST_RESHOW = "-1"
CANCEL = "-3"
WAITING_FOR_RESPONSE = "-9"


class Response:
    def __init__(
        self,
        selection: Optional[list[str]] = None,
        text: Optional[str] = None,
        masked_image: Optional[str] = None,
        masked_data: Optional[str] = None,
        extras: Optional[tuple[str, str, str]] = None,
        choice_index: Optional[int] = None,
    ):
        self.selection = [int(value) for value in selection] if selection else []
        self.text = text
        self.masked_image = masked_image
        self.masked_data = masked_data
        self.extras = extras
        self.choice_index = int(choice_index) if choice_index is not None else None

    def get_extras(self, defaults: tuple[str, str, str]) -> tuple[str, str, str]:
        return self.extras or defaults


class TimeoutResponse(Response):
    pass


class CancelledResponse(Response):
    pass


class RequestResponse(Response):
    pass


class MessageState:
    _latest: Optional["MessageState"] = None
    graph_id_expected = None

    def __init__(self, data: dict | str | None = None):
        data_dict = dict(data or {}) if isinstance(data, dict) else json.loads(data or "{}")
        self.graph_id = data_dict.pop("graph_id", None)
        self.special = data_dict.pop("special", None)
        self.response = Response(**data_dict)

    @classmethod
    def latest(cls) -> "MessageState":
        if cls._latest is None:
            cls._latest = cls()
        return cls._latest

    @classmethod
    def start_waiting(cls, graph_id):
        cls._latest = cls({"special": WAITING_FOR_RESPONSE})
        cls.graph_id_expected = graph_id

    @classmethod
    def stop_waiting(cls):
        cls._latest = cls()
        cls.graph_id_expected = None

    @classmethod
    def waiting(cls) -> bool:
        return cls.latest().special == WAITING_FOR_RESPONSE

    @classmethod
    def get_response(cls) -> Response:
        latest = cls.latest()
        if cls.waiting():
            return TimeoutResponse()
        if latest.special == CANCEL:
            return CancelledResponse()
        if latest.special == REQUEST_RESHOW:
            return RequestResponse()
        return latest.response


async def pepe_image_filter_message(request):
    post = await request.post()
    message = MessageState(post.get("response"))

    if str(MessageState.graph_id_expected) == str(message.graph_id):
        if MessageState.waiting():
            MessageState._latest = message
        else:
            print("Ignoring Pepe Image Filter response because no request is waiting")
    else:
        print("Ignoring mismatched Pepe Image Filter response")

    return web.json_response({})


def register_message_route():
    """Register the response endpoint when the ComfyUI server singleton exists."""
    server = getattr(PromptServer, "instance", None)
    if server is not None:
        server.routes.post("/pepe-image-filter-message")(pepe_image_filter_message)


register_message_route()


def wait_for_response(seconds, graph_id) -> Response:
    MessageState.start_waiting(graph_id)
    try:
        end_time = time.monotonic() + seconds
        while time.monotonic() < end_time and MessageState.waiting():
            throw_exception_if_processing_interrupted()
            PromptServer.instance.send_sync(
                "pepe-image-filter-images",
                {"tick": int(end_time - time.monotonic()), "graph_id": graph_id},
            )
            time.sleep(0.5)
        if MessageState.waiting():
            PromptServer.instance.send_sync(
                "pepe-image-filter-images", {"timeout": True, "graph_id": graph_id}
            )
        return MessageState.get_response()
    finally:
        MessageState.stop_waiting()


def send_and_wait(payload, timeout, graph_id) -> Response:
    payload["graph_id"] = graph_id

    while True:
        PromptServer.instance.send_sync("pepe-image-filter-images", payload)
        response = wait_for_response(timeout, graph_id)
        if isinstance(response, CancelledResponse):
            raise InterruptProcessingException()
        if not isinstance(response, RequestResponse):
            return response
