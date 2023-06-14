from typing import Awaitable, Callable

from port_ocean.models.diff import Change

RESYNC_EVENT_LISTENER = Callable[[str], Awaitable[Change]]
START_EVENT_LISTENER = Callable[[], Awaitable]
