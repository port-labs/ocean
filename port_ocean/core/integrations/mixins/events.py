from collections import defaultdict
from typing import Any, Callable

from loguru import logger

from port_ocean.core.ocean_types import (
    IntegrationEventsCallbacks,
    START_EVENT_LISTENER,
    RESYNC_EVENT_LISTENER,
    BEFORE_RESYNC_EVENT_LISTENER,
    AFTER_RESYNC_EVENT_LISTENER,
    EventListenerType,
)


class EventsMixin:
    """A mixin class that provides event handling capabilities for the integration class.

    This mixin allows classes to register event listeners and manage event callbacks.
    It provides methods for attaching listeners to various lifecycle events.

    Attributes:
        event_strategy: A dictionary storing event callbacks for different event types.
    """

    def __init__(self) -> None:
        self.event_strategy: IntegrationEventsCallbacks = {
            "start": [],
            "start_for_listener": defaultdict(list),  # New: event listener-specific start functions
            "resync": defaultdict(list),
            "resync_start": [],
            "resync_complete": [],
        }

    @property
    def available_resync_kinds(self) -> list[str]:
        return list(self.event_strategy["resync"].keys())

    def on_start(
        self,
        function: START_EVENT_LISTENER | None = None,
        event_listener: EventListenerType | None = None
    ) -> START_EVENT_LISTENER | Callable[[START_EVENT_LISTENER], START_EVENT_LISTENER]:
        """Register a function as a listener for the "start" event.

        Args:
            function: The function to register (when used directly)
            event_listener: Optional event listener type to register for specific startup behavior.
                          Accepts both EventListenerType enum values and string literals.

        Returns:
            The original function or a decorator function

        Usage:
            # General startup (fallback)
            @ocean.on_start()
            async def on_start() -> None:
                pass

            @ocean.on_start(event_listener=EventListenerType.ONCE)
            async def on_start_once() -> None:
                pass

            @ocean.on_start(event_listener=EventListenerType.WEBHOOK_ONLY)
            @ocean.on_start(event_listener=EventListenerType.POLLING)
            async def on_start_webhook_and_polling() -> None:
                if is_webhook_exists():
                    await verify_webhook_connection()
                else:
                    await setup_webhook()


        """
        def decorator(func: START_EVENT_LISTENER) -> START_EVENT_LISTENER:
            if event_listener is not None:
                # Convert enum to string value for storage
                listener_key = event_listener.value if isinstance(event_listener, EventListenerType) else event_listener
                logger.debug(f"Registering {func} as a start event listener for {listener_key}")
                self.event_strategy["start_for_listener"][listener_key].append(func)
            else:
                logger.debug(f"Registering {func} as a general start event listener")
                self.event_strategy["start"].append(func)
            return func

        if function is not None:
            # Called directly without parentheses: @ocean.on_start
            return decorator(function)
        else:
            # Called with parentheses: @ocean.on_start() or @ocean.on_start(event_listener=EventListenerType.ONCE)
            return decorator

    def on_resync(
        self, function: RESYNC_EVENT_LISTENER | None, kind: str | None = None
    ) -> RESYNC_EVENT_LISTENER | None:
        """Register a function as a listener for a "resync" event."""
        if function is not None:
            if kind is None:
                logger.debug("Registering resync event listener any kind")
            else:
                logger.info(f"Registering resync event listener for kind {kind}")
            self.event_strategy["resync"][kind].append(function)
        return function

    def on_resync_start(
        self, function: BEFORE_RESYNC_EVENT_LISTENER | None
    ) -> BEFORE_RESYNC_EVENT_LISTENER | None:
        """Register a function to be called when a resync operation starts."""
        if function is not None:
            logger.debug(f"Registering {function} as a resync_start event listener")
            self.event_strategy["resync_start"].append(function)
        return function

    def on_resync_complete(
        self, function: AFTER_RESYNC_EVENT_LISTENER | None
    ) -> AFTER_RESYNC_EVENT_LISTENER | None:
        """Register a function to be called when a resync operation completes."""
        if function is not None:
            logger.debug(f"Registering {function} as a resync_complete event listener")
            self.event_strategy["resync_complete"].append(function)
        return function
