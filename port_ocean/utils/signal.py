import signal
from typing import Callable

from werkzeug.local import LocalProxy, LocalStack

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


_signal_handler = LocalStack()


def _get_signal_handler():
    global _signal_handler
    if _signal_handler.top is None:
        raise RuntimeError("Signal handler is not initialized")
    return _signal_handler.top


signal_handler = LocalProxy(_get_signal_handler)


def init_signal_handler():
    global _signal_handler
    if _signal_handler.top is not None:
        raise RuntimeError("Signal handler is already initialized")
    _signal_handler.push(SignalHandler())
