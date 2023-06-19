from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator

from werkzeug.local import LocalStack, LocalProxy

from port_ocean.context.integration import ocean
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
)
from port_ocean.errors import EventContextNotFoundError


@dataclass
class EventContext:
    event_type: str
    _port_app_config: PortAppConfig | None = field(default=None)

    @property
    def port_app_config(self) -> PortAppConfig:
        if self._port_app_config is None:
            raise ValueError("Port app config is not set")
        return self._port_app_config


_event_context_stack: LocalStack[EventContext] = LocalStack()


def _get_event_context() -> EventContext:
    """
    Get the event context from the current thread.
    """
    event_context = _event_context_stack.top
    if event_context is not None:
        return event_context

    raise EventContextNotFoundError(
        "You must be inside an event context in order to use it"
    )


event: EventContext = LocalProxy(lambda: _get_event_context())  # type: ignore


@asynccontextmanager
async def event_context(
    kind: str, port_app_config: PortAppConfig | None = None
) -> AsyncIterator[EventContext]:
    if port_app_config is None:
        port_app_config = (
            await ocean.integration.port_app_config_handler.get_port_app_config()
        )
    _event_context_stack.push(EventContext(kind, _port_app_config=port_app_config))

    yield event

    _event_context_stack.pop()
