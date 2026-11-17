from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def resolve_effective_datetime(
    cursor: datetime | None,
    selector_value: datetime | None,
) -> datetime | None:
    """Prefer the incremental cursor over a selector-derived datetime."""
    if cursor is not None:
        return cursor
    return selector_value


def is_pushed_since(repo: dict[str, Any], since: datetime) -> bool:
    """Whether the repository's pushed_at is at or after *since*.

    Repositories that were never pushed (no pushed_at) are not.
    """
    pushed_at = repo.get("pushed_at")
    if not pushed_at:
        return False
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(pushed_at) >= since
