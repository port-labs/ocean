from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock

import pytest

from aws.webhook.session_resolver import AccountSessionResolver


async def _make_source(accounts: dict[str, AsyncMock]):
    async def source() -> AsyncIterator:
        for account_id, session in accounts.items():
            yield {"Id": account_id, "Name": f"acct-{account_id}"}, session

    return source


@pytest.mark.asyncio
async def test_known_account_returns_session() -> None:
    sess_a = AsyncMock(name="A")
    sess_b = AsyncMock(name="B")
    source = await _make_source({"111": sess_a, "222": sess_b})
    resolver = AccountSessionResolver(source=source)
    assert await resolver.get("111") is sess_a
    assert await resolver.get("222") is sess_b


@pytest.mark.asyncio
async def test_unknown_account_returns_none_and_refreshes_once() -> None:
    """An unknown account triggers a refresh; if still missing, return None."""
    refreshes = 0
    sess_a = AsyncMock(name="A")

    async def source() -> AsyncIterator:
        nonlocal refreshes
        refreshes += 1
        yield {"Id": "111", "Name": "acct-111"}, sess_a

    resolver = AccountSessionResolver(source=source)
    assert await resolver.get("999") is None
    # First call: initial populate + miss refresh = 2 calls.
    assert refreshes == 2


@pytest.mark.asyncio
async def test_empty_account_id_returns_none() -> None:
    resolver = AccountSessionResolver(source=await _make_source({}))
    assert await resolver.get("") is None


@pytest.mark.asyncio
async def test_invalidate_forces_refresh() -> None:
    refreshes = 0
    sess_a = AsyncMock(name="A")

    async def source() -> AsyncIterator:
        nonlocal refreshes
        refreshes += 1
        yield {"Id": "111", "Name": "acct-111"}, sess_a

    resolver = AccountSessionResolver(source=source)
    await resolver.get("111")  # populate
    await resolver.get("111")  # cached, no extra source call
    resolver.invalidate()
    await resolver.get("111")  # refresh
    assert refreshes == 2
