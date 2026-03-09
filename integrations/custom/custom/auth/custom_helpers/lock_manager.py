"""Manages re-authentication lock to prevent concurrent re-auth attempts."""

import asyncio


class LockManager:
    """Manages re-authentication lock to prevent concurrent re-auth attempts."""

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
