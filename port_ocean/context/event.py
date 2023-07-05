from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator, Literal, Any, TYPE_CHECKING, Optional
from uuid import uuid4

from loguru import logger
from werkzeug.local import LocalStack, LocalProxy

from port_ocean.exceptions.context import EventContextNotFoundError
from port_ocean.utils import get_time

if TYPE_CHECKING:
    from port_ocean.core.handlers.port_app_config.models import PortAppConfig

TriggerType = Literal["manual", "machine", "request"]


class EventType:
    START = "start"
    RESYNC = "resync"
    HTTP_REQUEST = "http_request"


@dataclass
class EventContext:
    event_type: str
    trigger_type: TriggerType = "machine"
    attributes: dict[str, Any] = field(default_factory=dict)
    _port_app_config: Optional["PortAppConfig"] = None
    _parent_event: Optional["EventContext"] = None
    _event_id: str = field(default_factory=lambda: str(uuid4()))

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
) -> AsyncIterator[EventContext]:
    attributes = attributes or {}

    parent = _event_context_stack.top

    _event_context_stack.push(
        EventContext(
            event_type,
            trigger_type=trigger_type,
            attributes=attributes,
            _parent_event=parent,
        )
    )

    start_time = get_time(seconds_precision=False)
    with logger.contextualize(
        event_trigger_type=event.trigger_type,
        event_kind=event.event_type,
        event_id=event.id,
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

    _event_context_stack.pop()
