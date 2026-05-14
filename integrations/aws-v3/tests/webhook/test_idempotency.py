import asyncio

import pytest

from aws.webhook.idempotency import InMemoryIdempotencyStore


@pytest.mark.asyncio
async def test_first_seen_returns_false_then_true() -> None:
    store = InMemoryIdempotencyStore()
    assert await store.seen_or_record("m1") is False
    assert await store.seen_or_record("m1") is True


@pytest.mark.asyncio
async def test_empty_id_is_never_recorded() -> None:
    store = InMemoryIdempotencyStore()
    # Empty MessageId never dedups — don't silently swallow events that lack one.
    assert await store.seen_or_record("") is False
    assert await store.seen_or_record("") is False


@pytest.mark.asyncio
async def test_max_entries_evicts_oldest() -> None:
    store = InMemoryIdempotencyStore(max_entries=2)
    await store.seen_or_record("a")
    await store.seen_or_record("b")
    await store.seen_or_record("c")  # cache is now {b, c}; "a" evicted
    # "a" is gone — re-recording it now treats it as new, which evicts "b".
    assert await store.seen_or_record("a") is False
    # "c" is the only id from the original three still in cache.
    assert await store.seen_or_record("c") is True


@pytest.mark.asyncio
async def test_ttl_expiry_treats_old_id_as_new(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryIdempotencyStore(ttl_seconds=0.0)
    assert await store.seen_or_record("m") is False
    # With ttl=0, the next call sees the entry as expired and re-records it.
    assert await store.seen_or_record("m") is False


@pytest.mark.asyncio
async def test_concurrent_writes_serialise() -> None:
    store = InMemoryIdempotencyStore()
    results = await asyncio.gather(*[store.seen_or_record("m") for _ in range(50)])
    # Exactly one caller sees "first" (False); all others see duplicates (True).
    assert results.count(False) == 1
    assert results.count(True) == 49
