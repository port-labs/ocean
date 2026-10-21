from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


def _monotonic() -> float:
    return time.monotonic()


@dataclass(frozen=True)
class _Entry(Generic[T]):
    value: T
    cached_at: float


class Cache(Generic[T]):
    """In-memory cache with TTL expiry and LRU eviction.

    Opt-in at call sites — do not wrap ``AnthropicClient`` get methods so those
    stay fresh.
    """

    def __init__(self, ttl_seconds: float, max_items: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        if max_items < 1:
            raise ValueError("max_items must be >= 1")
        self._ttl = ttl_seconds
        self._max_items = max_items
        self._store: OrderedDict[str, _Entry[T]] = OrderedDict()

    def get(self, key: str) -> T | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if _monotonic() - entry.cached_at >= self._ttl:
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return entry.value

    def set(self, key: str, value: T) -> None:
        self._store[key] = _Entry(value=value, cached_at=_monotonic())
        self._store.move_to_end(key)
        while len(self._store) > self._max_items:
            self._store.popitem(last=False)

    async def get_or_fetch(
        self, key: str, fetch: Callable[[], Awaitable[T]]
    ) -> T:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = await fetch()
        self.set(key, value)
        return value
