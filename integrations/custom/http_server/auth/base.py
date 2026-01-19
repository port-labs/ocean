"""
Base authentication handler class.
"""

import httpx
from typing import Dict, Any


class AuthHandler:
    """Base class for authentication handlers"""

    def __init__(self, client: httpx.AsyncClient, config: Dict[str, Any]):
        self.client = client
        self.config = config
        self._is_async_setup = False

    def setup(self) -> None:
        """Setup authentication synchronously - override in subclasses for sync setup"""
        pass

    async def async_setup(self) -> None:
        """Setup authentication asynchronously - override in subclasses for async setup"""
        pass

    async def reauthenticate(self) -> None:
        """Re-authenticate when token expires - override in subclasses that support re-auth"""
        pass

    @property
    def is_async_setup(self) -> bool:
        """Whether this handler requires async setup"""
        return self._is_async_setup
