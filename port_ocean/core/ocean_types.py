from __future__ import annotations

import typing
from collections import defaultdict
from dataclasses import dataclass, field
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Awaitable,
)

if typing.TYPE_CHECKING:
    from port_ocean.core.probe import ProbeContext

RAW_ITEM = dict[Any, Any]
RAW_RESULT = list[RAW_ITEM]
ASYNC_GENERATOR_RESYNC_TYPE = AsyncIterator[RAW_RESULT]
RESYNC_RESULT = list[RAW_ITEM | ASYNC_GENERATOR_RESYNC_TYPE]

LISTENER_RESULT = Awaitable[RAW_RESULT] | ASYNC_GENERATOR_RESYNC_TYPE
RESYNC_EVENT_LISTENER = Callable[[str], LISTENER_RESULT]
INCREMENTAL_EVENT_LISTENER = Callable[[str], LISTENER_RESULT]
START_EVENT_LISTENER = Callable[[], Awaitable[None]]

BEFORE_RESYNC_EVENT_LISTENER = Callable[[], Awaitable[None]]
AFTER_RESYNC_EVENT_LISTENER = Callable[[], Awaitable[None]]

ON_PROBE_EVENT_LISTENER = Callable[["ProbeContext"], Awaitable["ProbeContext | None"]]


class ETLPhase:
    EXTRACT = "extract"
    RECONCILIATION = "reconciliation"


@dataclass
class IntegrationEventsCallbacks:
    start: list[START_EVENT_LISTENER] = field(default_factory=list)
    resync: dict[str | None, list[RESYNC_EVENT_LISTENER]] = field(
        default_factory=lambda: defaultdict(list)
    )
    resync_start: list[BEFORE_RESYNC_EVENT_LISTENER] = field(default_factory=list)
    resync_complete: list[AFTER_RESYNC_EVENT_LISTENER] = field(default_factory=list)
    incremental: dict[str | None, list[INCREMENTAL_EVENT_LISTENER]] = field(
        default_factory=lambda: defaultdict(list)
    )
    on_probe: ON_PROBE_EVENT_LISTENER | None = None
