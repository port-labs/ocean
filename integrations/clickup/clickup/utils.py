from datetime import datetime


def timestamp_to_datetime(timestamp: str) -> str | None:
    """Convert a timestamp to a datetime object."""
    if not timestamp:
        return None
    return datetime.fromtimestamp(int(timestamp) / 1000).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )
