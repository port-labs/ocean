from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator, Literal, Any, TYPE_CHECKING, Optional

from werkzeug.local import LocalStack, LocalProxy

from port_ocean.errors import EventContextNotFoundError

if TYPE_CHECKING:
    from port_ocean.core.handlers.port_app_config.models import PortAppConfig

TriggerType = Literal["manual", "machine"]


@dataclass
class EventContext:
    event_type: str
    trigger_type: TriggerType = "machine"
    attributes: dict[str, Any] = field(default_factory=dict)
    _port_app_config: Optional["PortAppConfig"] = field(default=None)

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
    if top_event_context is not None:
        return top_event_context

    raise EventContextNotFoundError(
        "You must be inside an event context in order to use it"
    )


event: EventContext = LocalProxy(lambda: _get_event_context())  # type: ignore


@asynccontextmanager
async def event_context(
    kind: str,
    trigger_type: TriggerType = "manual",
    attributes: dict[str, Any] | None = None,
) -> AsyncIterator[EventContext]:
    if attributes is None:
        attributes = {}

    _event_context_stack.push(
        EventContext(
            kind,
            trigger_type=trigger_type,
            attributes=attributes,
        )
    )

    yield event

    _event_context_stack.pop()
