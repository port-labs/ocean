import re
from urllib.parse import urlparse

_LIVE_EVENTS_UUID_PATTERN = re.compile(r"/live-events/([^/]+)")


def resolve_live_events_stream_key_from_base_url(base_url: str) -> str:
    """Derive the Redis stream key from an integration base URL.

    The base URL must contain ``/live-events/{uuid}``, for example::

        https://host.example.com/live-events/1111111/webhook
        -> 1111111/live-events/raw/event-stream
    """
    if not base_url:
        raise ValueError(
            "base_url is required to resolve the Redis live events stream key"
        )

    path = urlparse(base_url).path
    match = _LIVE_EVENTS_UUID_PATTERN.search(path)
    if not match:
        raise ValueError(
            "base_url must include /live-events/{uuid} "
            f"(e.g. https://host/live-events/your-uuid). Got: {base_url!r}"
        )

    return f"{match.group(1)}/live-events/raw/event-stream"
