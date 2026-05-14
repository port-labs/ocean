from __future__ import annotations

import asyncio
from typing import AsyncIterator, Callable

from aiobotocore.session import AioSession
from loguru import logger

from aws.auth.session_factory import AccountInfo, get_all_account_sessions


SessionMap = dict[str, AioSession]
SessionSourceFn = Callable[[], AsyncIterator[tuple[AccountInfo, AioSession]]]


class AccountSessionResolver:
    """Account-id → AioSession lookup with refresh-on-miss.

    Safe across asyncio tasks via a single async lock around cache
    mutation. Reads against a populated cache are lock-free — dict key
    lookup is atomic in CPython.
    """

    def __init__(self, source: SessionSourceFn | None = None) -> None:
        self._source = source or get_all_account_sessions
        self._sessions: SessionMap = {}
        self._lock = asyncio.Lock()
        self._populated = False

    async def get(self, account_id: str) -> AioSession | None:
        if not account_id:
            return None
        if not self._populated:
            await self._refresh()
        session = self._sessions.get(account_id)
        if session is not None:
            return session
        # Miss can mean a newly-added org member; one refresh attempt.
        logger.info(
            f"AccountSessionResolver: cache miss for {account_id}, refreshing"
        )
        await self._refresh()
        return self._sessions.get(account_id)

    async def _refresh(self) -> None:
        async with self._lock:
            new_map: SessionMap = {}
            async for account, session in self._source():
                new_map[account["Id"]] = session
            self._sessions = new_map
            self._populated = True

    def invalidate(self) -> None:
        """Force the next `get()` to repopulate from source."""
        self._populated = False
        self._sessions = {}
