from dataclasses import dataclass

from werkzeug.local import LocalStack, LocalProxy

_event_context_stack = LocalStack()


class NoContextError(Exception):
    pass


class EventContextNotFoundError(NoContextError):
    pass


@dataclass
class EventContext:
    event_type: str
    kind: str
    data: dict | None
    port_app_config: dict


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


event: EventContext = LocalProxy(lambda: _get_event_context())
