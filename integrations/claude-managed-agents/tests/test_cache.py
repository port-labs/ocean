from typing import Any
from unittest.mock import AsyncMock

import pytest

from utils.cache import Cache


@pytest.mark.asyncio
async def test_get_or_fetch_returns_cached_value() -> None:
    cache: Cache[str] = Cache(ttl_seconds=60.0, max_items=8)
    fetch = AsyncMock(return_value="agent")

    assert await cache.get_or_fetch("a1", fetch) == "agent"
    assert await cache.get_or_fetch("a1", fetch) == "agent"
    fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_or_fetch_refetches_after_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    cache: Cache[str] = Cache(ttl_seconds=10.0, max_items=8)
    fetch = AsyncMock(side_effect=["first", "second"])
    now = 1000.0
    monkeypatch.setattr("utils.cache._monotonic", lambda: now)

    assert await cache.get_or_fetch("a1", fetch) == "first"
    now = 1011.0
    assert await cache.get_or_fetch("a1", fetch) == "second"
    assert fetch.await_count == 2


@pytest.mark.asyncio
async def test_get_or_fetch_evicts_lru_when_over_max_items() -> None:
    cache: Cache[str] = Cache(ttl_seconds=60.0, max_items=2)
    fetch_a = AsyncMock(return_value="a")
    fetch_b = AsyncMock(return_value="b")
    fetch_c = AsyncMock(return_value="c")

    await cache.get_or_fetch("a", fetch_a)
    await cache.get_or_fetch("b", fetch_b)
    # Touch a so b becomes LRU
    await cache.get_or_fetch("a", fetch_a)
    await cache.get_or_fetch("c", fetch_c)

    fetch_b_again = AsyncMock(return_value="b2")
    assert await cache.get_or_fetch("b", fetch_b_again) == "b2"
    fetch_b_again.assert_awaited_once()
    fetch_a.assert_awaited_once()


def test_get_and_set_round_trip() -> None:
    cache: Cache[str] = Cache(ttl_seconds=60.0, max_items=8)
    assert cache.get("missing") is None
    cache.set("k", "v")
    assert cache.get("k") == "v"


def test_rejects_invalid_constructor_args() -> None:
    with pytest.raises(ValueError):
        Cache[Any](ttl_seconds=0, max_items=1)
    with pytest.raises(ValueError):
        Cache[Any](ttl_seconds=1.0, max_items=0)
