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
)
from uuid import uuid4

from loguru import logger
from port_ocean.core.utils.entity_topological_sorter import EntityTopologicalSorter
from pydispatch import dispatcher  # type: ignore
from werkzeug.local import LocalStack, LocalProxy

from port_ocean.context.resource import resource
from port_ocean.exceptions.api import EmptyPortAppConfigError
from port_ocean.exceptions.context import (
    EventContextNotFoundError,
    ResourceContextNotFoundError,
)
from port_ocean.utils.misc import get_time


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
    entity_topological_sorter: EntityTopologicalSorter = field(
        default_factory=EntityTopologicalSorter
    )

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
    entity_topological_sorter = (
        parent.entity_topological_sorter
        if parent and parent.entity_topological_sorter
        else EntityTopologicalSorter()
    )

    attributes = {**parent_attributes, **(attributes or {})}

    new_event = EventContext(
        event_type,
        trigger_type=trigger_type,
        attributes=attributes,
        _parent_event=parent,
        # inherit port app config from parent event, so it can be used in nested events
        _port_app_config=parent.port_app_config if parent else None,
        entity_topological_sorter=entity_topological_sorter,
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
        except EmptyPortAppConfigError as e:
            logger.error(
                f"Skipping resync due to empty mapping: {str(e)}", exc_info=True
            )
            raise
        except BaseException as e:
            success = False
            if isinstance(e, KeyboardInterrupt):
                logger.warning("Operation interrupted by user", exc_info=True)
            elif isinstance(e, asyncio.CancelledError):
                logger.warning("Operation was cancelled", exc_info=True)
            else:
                logger.error(f"Event failed with error: {repr(e)}", exc_info=True)
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
