from collections import defaultdict
from typing import Any

from loguru import logger

from port_ocean.core.ocean_types import (
    IntegrationEventsCallbacks,
    START_EVENT_LISTENER,
    RESYNC_EVENT_LISTENER,
    BEFORE_RESYNC_EVENT_LISTENER,
    AFTER_RESYNC_EVENT_LISTENER,
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
            "resync": defaultdict(list),
            "resync_start": [],
            "resync_complete": [],
        }

    @property
    def available_resync_kinds(self) -> list[str]:
        return list(self.event_strategy["resync"].keys())

    def on_start(self, function: START_EVENT_LISTENER) -> START_EVENT_LISTENER:
        """Register a function as a listener for the "start" event."""
        logger.debug(f"Registering {function} as a start event listener")
        self.event_strategy["start"].append(function)
        return function

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
