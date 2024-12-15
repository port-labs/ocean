import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import (
    AsyncIterator,
    Literal,
    Any,
    TYPE_CHECKING,
    Optional,
    Callable,
    Awaitable,
    Union,
    Tuple,
    Coroutine,
)
from uuid import uuid4

from loguru import logger
from pydispatch import dispatcher  # type: ignore
from werkzeug.local import LocalStack, LocalProxy

from port_ocean.context.resource import resource
from port_ocean.exceptions.context import (
    EventContextNotFoundError,
    ResourceContextNotFoundError,
)
from port_ocean.utils.misc import get_time
from port_ocean.core.handlers.entities_state_applier.port.order_by_entities_dependencies import (
    order_by_entities_dependencies,
)
from port_ocean.core.models import Entity

if TYPE_CHECKING:
    from port_ocean.core.handlers.port_app_config.models import (
        ResourceConfig,
        PortAppConfig,
    )

TriggerType = Literal["manual", "machine", "request"]
AbortCallbackFunction = Callable[[], Union[Any, Awaitable[Any]]]


class EventType:
    START = "start"
    RESYNC = "resync"
    HTTP_REQUEST = "http_request"


@dataclass
class EventContext:
    event_type: str
    trigger_type: TriggerType = "machine"
    attributes: dict[str, Any] = field(default_factory=dict)
    _aborted: bool = False
    _port_app_config: Optional["PortAppConfig"] = None
    _parent_event: Optional["EventContext"] = None
    _event_id: str = field(default_factory=lambda: str(uuid4()))
    _on_abort_callbacks: list[AbortCallbackFunction] = field(default_factory=list)
    _failed_entity_callback_list: list[
        Tuple[Entity, Callable[[], Coroutine[Any, Any, Entity | Literal[False] | None]]]
    ] = field(default_factory=list)

    def register_failed_upsert_call_arguments(
        self,
        entity: Entity,
        func: Callable[[], Coroutine[Any, Any, Entity | Literal[False] | None]],
    ) -> None:
        self._failed_entity_callback_list.append((entity, func))

    async def handle_failed(self) -> None:
        entity_map: dict[
            str, Callable[[], Coroutine[Any, Any, Entity | Literal[False] | None]]
        ] = {
            f"{obj.identifier}-{obj.blueprint}": func
            for obj, func in self._failed_entity_callback_list
        }
        entity_list: list[Entity] = [
            obj for obj, func in self._failed_entity_callback_list
        ]

        sorted_and_mapped = order_by_entities_dependencies(entity_list)
        for obj in sorted_and_mapped:
            func = entity_map.get(f"{obj.identifier}-{obj.blueprint}")
            if func is not None:
                await func()

    async def handle_failed_no_sort(self) -> None:
        for obj, func in self._failed_entity_callback_list:
            await func()

    def on_abort(self, func: AbortCallbackFunction) -> None:
        self._on_abort_callbacks.append(func)

    def abort(self) -> None:
        for func in self._on_abort_callbacks:
            try:
                if asyncio.iscoroutinefunction(func):
                    asyncio.get_running_loop().run_until_complete(func())
                else:
                    func()
            except Exception as ex:
                logger.warning(
                    f"Failed to call one of the abort callbacks {ex}", exc_info=True
                )
        self._aborted = True

    @property
    def aborted(self) -> bool:
        return self._aborted

    @property
    def resource_config(self) -> Optional["ResourceConfig"]:
        try:
            return resource.resource_config
        except ResourceContextNotFoundError:
            return None

    @property
    def id(self) -> str:
        return self._event_id

    @property
    def parent(self) -> Optional["EventContext"]:
        return self._parent_event

    @property
    def parent_id(self) -> Optional[str]:
        return self._parent_event.id if self._parent_event else None

    @property
    def port_app_config(self) -> "PortAppConfig":
        if self._port_app_config is None:
            raise ValueError("Port app config is not set")
        return self._port_app_config

    @port_app_config.setter
    def port_app_config(self, value: "PortAppConfig") -> None:
        self._port_app_config = value


_event_context_stack: LocalStack[EventContext] = LocalStack()


def _get_event_context() -> EventContext:
    """
    Get the event context from the current thread.
    """
    top_event_context = _event_context_stack.top
    if top_event_context is None:
        raise EventContextNotFoundError(
            "You must be inside an event context in order to use it"
        )

    return top_event_context


event: EventContext = LocalProxy(lambda: _get_event_context())  # type: ignore


@asynccontextmanager
async def event_context(
    event_type: str,
    trigger_type: TriggerType = "manual",
    attributes: dict[str, Any] | None = None,
    parent_override: EventContext | None = None,
) -> AsyncIterator[EventContext]:
    parent = parent_override or _event_context_stack.top
    parent_attributes = parent.attributes if parent else {}

    attributes = {**parent_attributes, **(attributes or {})}
    new_event = EventContext(
        event_type,
        trigger_type=trigger_type,
        attributes=attributes,
        _parent_event=parent,
        # inherit port app config from parent event, so it can be used in nested events
        _port_app_config=parent.port_app_config if parent else None,
    )
    _event_context_stack.push(new_event)

    def _handle_event(triggering_event_id: int) -> None:
        if (
            new_event.event_type == EventType.RESYNC
            and new_event.id != triggering_event_id
        ):
            logger.warning("ABORTING RESYNC EVENT DUE TO NEWER RESYNC REQUEST")
            new_event.abort()

    dispatcher.connect(_handle_event, event_type)
    dispatcher.send(event_type, triggering_event_id=event.id)

    start_time = get_time(seconds_precision=False)
    with logger.contextualize(
        event_trigger_type=event.trigger_type,
        event_kind=event.event_type,
        event_id=event.id,
        event_parent_id=event.parent_id,
        event_resource_kind=(
            event.resource_config.kind if event.resource_config else None
        ),
    ):
        logger.info("Event started")
        try:
            yield event
        except:
            success = False
            raise
        else:
            success = True
        finally:
            end_time = get_time(seconds_precision=False)
            time_elapsed = round(end_time - start_time, 5)
            logger.bind(
                success=success,
                time_elapsed=time_elapsed,
            ).info("Event finished")

            dispatcher.disconnect(_handle_event, event_type)

    _event_context_stack.pop()
