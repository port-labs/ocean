from dataclasses import dataclass, field

from werkzeug.local import LocalStack, LocalProxy

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.errors import EventContextNotFoundError


@dataclass
class EventContext:
    event_type: str
    _resource_config: ResourceConfig | None = field(default=None)
    _port_app_config: PortAppConfig | None = field(default=None)

    @property
    def resource_config(self) -> ResourceConfig:
        if self._resource_config is None:
            raise ValueError("Resource config is not set")
        return self._resource_config

    @property
    def port_app_config(self) -> PortAppConfig:
        if self._port_app_config is None:
            raise ValueError("Port app config is not set")
        return self._port_app_config


_event_context_stack: LocalStack[EventContext] = LocalStack()


def initialize_event_context(event_context: EventContext) -> None:
    """
    This Function initiates the event context and pushes it into the LocalStack().
    """
    _event_context_stack.push(event_context)


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
