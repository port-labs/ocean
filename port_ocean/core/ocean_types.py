from typing import (
    TypedDict,
    Any,
    AsyncIterator,
    Callable,
    Awaitable,
    NamedTuple,
)

from dataclasses import field
from port_ocean.core.models import Entity

RAW_ITEM = dict[Any, Any]
RAW_RESULT = list[RAW_ITEM]
ASYNC_GENERATOR_RESYNC_TYPE = AsyncIterator[RAW_RESULT]
RESYNC_RESULT = list[RAW_ITEM | ASYNC_GENERATOR_RESYNC_TYPE]

LISTENER_RESULT = Awaitable[RAW_RESULT] | ASYNC_GENERATOR_RESYNC_TYPE
RESYNC_EVENT_LISTENER = Callable[[str], LISTENER_RESULT]
START_EVENT_LISTENER = Callable[[], Awaitable[None]]

BEFORE_RESYNC_EVENT_LISTENER = Callable[[], Awaitable[None]]
AFTER_RESYNC_EVENT_LISTENER = Callable[[], Awaitable[None]]


class RawEntityDiff(TypedDict):
    before: list[RAW_ITEM]
    after: list[RAW_ITEM]


class EntityDiff(TypedDict):
    before: list[Entity]
    after: list[Entity]


class EntitySelectorDiff(NamedTuple):
    passed: list[Entity]
    failed: list[Entity]


class CalculationResult(NamedTuple):
    entity_selector_diff: EntitySelectorDiff
    errors: list[Exception]
    number_of_transformed_entities: int = 0
    misonfigured_entity_keys: dict[str, str] = field(default_factory=dict)


class IntegrationEventsCallbacks(TypedDict):
    start: list[START_EVENT_LISTENER]
    resync: dict[str | None, list[RESYNC_EVENT_LISTENER]]
    resync_start: list[BEFORE_RESYNC_EVENT_LISTENER]
    resync_complete: list[AFTER_RESYNC_EVENT_LISTENER]
