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

    def setup(self) -> None:
        """Setup authentication synchronously - override in subclasses for sync setup"""
        pass
