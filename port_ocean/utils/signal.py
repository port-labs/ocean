from asyncio import iscoroutinefunction
from typing import Callable, Any

from werkzeug.local import LocalProxy, LocalStack

from port_ocean.exceptions.utils import (
    SignalHandlerNotInitialized,
    SignalHandlerAlreadyInitialized,
)
from port_ocean.utils.misc import generate_uuid


class SignalHandler:
    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[], Any]] = {}

    async def exit(self) -> None:
        """
        Handles the exit signal.
        """
        while self._handlers:
            _, handler = self._handlers.popitem()
            if iscoroutinefunction(handler):
                await handler()
            else:
                handler()

    def register(self, callback: Callable[[], Any]) -> str:
        _id = generate_uuid()
        self._handlers[_id] = callback

        return _id

    def unregister(self, _id: str) -> None:
        del self._handlers[_id]


_signal_handler: LocalStack[SignalHandler] = LocalStack()


def _get_signal_handler() -> SignalHandler:
    global _signal_handler
    if _signal_handler.top is None:
        raise SignalHandlerNotInitialized("Signal handler is not initialized")
    return _signal_handler.top


signal_handler: SignalHandler = LocalProxy(_get_signal_handler)  # type: ignore


def init_signal_handler() -> None:
    global _signal_handler
    if _signal_handler.top is not None:
        raise SignalHandlerAlreadyInitialized("Signal handler is already initialized")
    _signal_handler.push(SignalHandler())
