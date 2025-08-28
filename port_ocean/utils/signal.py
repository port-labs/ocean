from asyncio import iscoroutinefunction
from typing import Any, Callable

from werkzeug.local import LocalProxy, LocalStack

from port_ocean.exceptions.utils import (
    SignalHandlerAlreadyInitialized,
    SignalHandlerNotInitialized,
)
from port_ocean.utils.misc import generate_uuid


class SignalHandler:
    def __init__(self) -> None:
        self._handlers: dict[str, tuple[Callable[[], Any], int]] = {}

    async def exit(self) -> None:
        """
        Handles the exit signal.
        Executes handlers in priority order (highest priority first).
        """
        # Sort handlers by priority (highest first) and execute them
        sorted_handlers = sorted(
            self._handlers.items(), key=lambda x: x[1][1], reverse=True
        )

        for _id, (handler, _) in sorted_handlers:
            if iscoroutinefunction(handler):
                await handler()
            else:
                handler()

    def register(self, callback: Callable[[], Any], priority: int = 0) -> str:
        """
        Register a callback with a priority.

        Args:
            callback: The callback function to register
            priority: Priority level (higher numbers execute first, default: 0)

        Returns:
            Unique identifier for the registered callback
        """
        _id = generate_uuid()
        self._handlers[_id] = (callback, priority)
        return _id

    def unregister(self, _id: str) -> None:
        """Unregister a callback by its ID."""
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
