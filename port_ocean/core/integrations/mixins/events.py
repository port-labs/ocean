from collections import defaultdict

from port_ocean.core.ocean_types import (
    IntegrationEventsCallbacks,
    START_EVENT_LISTENER,
    RESYNC_EVENT_LISTENER,
)


class EventsMixin:
    def __init__(self) -> None:
        self.event_strategy: IntegrationEventsCallbacks = {
            "start": [],
            "resync": defaultdict(list),
        }

    def on_start(self, func: START_EVENT_LISTENER) -> START_EVENT_LISTENER:
        self.event_strategy["start"].append(func)
        return func

    def on_resync(
        self, func: RESYNC_EVENT_LISTENER, kind: str | None = None
    ) -> RESYNC_EVENT_LISTENER:
        self.event_strategy["resync"][kind].append(func)
        return func
