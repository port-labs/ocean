import signal
from typing import Callable

from loguru import logger

from port_ocean.utils.misc import generate_uuid


class SignalHandler:
    def __init__(self):
        self._handlers: dict[str, Callable] = {}
        signal.signal(signal.SIGINT, lambda _, __: self._exit())
        signal.signal(signal.SIGTERM, lambda _, __: self._exit())

    def __call__(self, *args, **kwargs):
        return self

    def _exit(self) -> None:
        """
        Handles the exit signal.
        """
        while self._handlers:
            _, handler = self._handlers.popitem()
            handler()

    def register(self, callback: Callable) -> str:
        _id = generate_uuid()
        self._handlers[_id] = callback

        return _id

    def unregister(self, _id: str) -> None:
        del self._handlers[_id]


signal_handler = {}


def set_signal_handler():
    global signal_handler
    signal_handler["signal_handler"] = SignalHandler()
    logger.info(signal_handler)


def get_signal_handler():
    global signal_handler
    logger.info(signal_handler)
    return signal_handler["signal_handler"]


def register_signal_handler(callback: Callable) -> str:
    return get_signal_handler().register(callback)
