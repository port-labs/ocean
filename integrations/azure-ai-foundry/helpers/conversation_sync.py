from __future__ import annotations

from datetime import UTC, datetime, timedelta


def effective_conversation_cutoff(
    incremental_cursor: datetime | None,
    *,
    since_days: int | None,
) -> datetime | None:
    """Latest (most recent) cutoff: incremental cursor and/or relative ``since`` window."""
    bounds: list[datetime] = []
    if incremental_cursor is not None:
        bounds.append(incremental_cursor)
    if since_days is not None:
        bounds.append(datetime.now(UTC) - timedelta(days=since_days))
    if not bounds:
        return None
    return max(bounds)
