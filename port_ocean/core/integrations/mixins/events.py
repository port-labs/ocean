from collections import defaultdict

from port_ocean.core.ocean_types import (
    IntegrationEventsCallbacks,
    START_EVENT_LISTENER,
    RESYNC_EVENT_LISTENER,
)


class EventsMixin:
    """A mixin class that provides event handling capabilities for the integration class.

    This mixin allows classes to register event listeners and manage event callbacks.
    It provides methods for attaching listeners to "start" and "resync" events.

    Attributes:
        event_strategy (IntegrationEventsCallbacks): A dictionary storing event callbacks.
            - "start": List of functions to be called on "start" event.
            - "resync": Default dictionary mapping event kinds to lists of functions
                        to be called on "resync" events of the specified kind.
    """

    def __init__(self) -> None:
        self.event_strategy: IntegrationEventsCallbacks = {
            "start": [],
            "resync": defaultdict(list),
        }

    def on_start(self, func: START_EVENT_LISTENER) -> START_EVENT_LISTENER:
        """Register a function as a listener for the "start" event.

        Args:
            func (START_EVENT_LISTENER): The function to be called on the "start" event.

        Returns:
            START_EVENT_LISTENER: The input function, unchanged.
        """
        self.event_strategy["start"].append(func)
        return func

    def on_resync(
        self, func: RESYNC_EVENT_LISTENER, kind: str | None = None
    ) -> RESYNC_EVENT_LISTENER:
        """Register a function as a listener for a "resync" event.

        Args:
            func (RESYNC_EVENT_LISTENER): The function to be called on the "resync" event.
            kind (str | None, optional): The kind of "resync" event. Defaults to None.

        Returns:
            RESYNC_EVENT_LISTENER: The input function, unchanged.
        """
        self.event_strategy["resync"][kind].append(func)
        return func
