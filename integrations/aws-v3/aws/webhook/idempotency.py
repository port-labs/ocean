from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from typing import Final


_DEFAULT_TTL_SECONDS: Final[float] = 600.0
_DEFAULT_MAX_ENTRIES: Final[int] = 10_000


class InMemoryIdempotencyStore:
    """Lock-protected TTL LRU over message identifiers.

    `seen_or_record(message_id)` returns True if the id was already
    recorded within the TTL, False otherwise (and records it).
    """

    def __init__(
        self,
        ttl_seconds: float = _DEFAULT_TTL_SECONDS,
        max_entries: int = _DEFAULT_MAX_ENTRIES,
    ) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._entries: OrderedDict[str, float] = OrderedDict()
        self._lock = asyncio.Lock()

    async def seen_or_record(self, message_id: str) -> bool:
        if not message_id:
            return False
        now = time.monotonic()
        async with self._lock:
            self._evict_expired(now)
            if message_id in self._entries:
                self._entries.move_to_end(message_id)
                return True
            self._entries[message_id] = now
            if len(self._entries) > self._max:
                self._entries.popitem(last=False)
            return False

    def _evict_expired(self, now: float) -> None:
        cutoff = now - self._ttl
        # OrderedDict iterates in insertion order — head is oldest.
        while self._entries:
            key, ts = next(iter(self._entries.items()))
            if ts >= cutoff:
                return
            self._entries.popitem(last=False)
