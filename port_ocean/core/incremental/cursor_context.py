"""Per-kind incremental cursor for handler code.

The cursor is set for the duration of ``process_resource`` during
``sync_incremental()`` — no nested ``event_context`` required.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Iterator

_incremental_cursor: ContextVar[datetime | None] = ContextVar(
    "incremental_cursor", default=None
)


def active_incremental_cursor() -> datetime | None:
    """Return the cursor for the current incremental kind, or ``None`` on full resync."""
    return _incremental_cursor.get()


@contextmanager
def with_active_incremental_cursor(cursor: datetime) -> Iterator[None]:
    """Bind *cursor* for the current async task until the block exits."""
    previous_cursor = _incremental_cursor.get()
    _incremental_cursor.set(cursor)
    try:
        yield
    finally:
        _incremental_cursor.set(previous_cursor)
