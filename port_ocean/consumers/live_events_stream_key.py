import re
from urllib.parse import urlparse

from port_ocean.exceptions.live_events import (
    LiveEventsUuidNotFoundError,
    MissingLiveEventsBaseUrlError,
)

_LIVE_EVENTS_UUID_PATTERN = re.compile(r"/live-events/([^/]+)")


def resolve_live_events_stream_key_from_base_url(base_url: str) -> str:
    """Derive the Redis stream key from an integration base URL.

    The base URL must contain ``/live-events/{uuid}``, for example::

        https://host.example.com/live-events/1111111/webhook
        -> 1111111/live-events/raw/event-stream
    """
    if not base_url:
        raise MissingLiveEventsBaseUrlError()

    path = urlparse(base_url).path
    match = _LIVE_EVENTS_UUID_PATTERN.search(path)
    if not match:
        raise LiveEventsUuidNotFoundError(base_url)

    return f"{match.group(1)}/live-events/raw/event-stream"
