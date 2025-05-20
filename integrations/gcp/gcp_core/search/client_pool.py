from typing import Type, Optional, Dict, Any
import asyncio
from loguru import logger
from google.cloud.asset_v1 import AssetServiceAsyncClient
from google.cloud.resourcemanager_v3 import (
    FoldersAsyncClient,
    OrganizationsAsyncClient,
    ProjectsAsyncClient,
)
from google.pubsub_v1 import PublisherAsyncClient, SubscriberAsyncClient


class ClientPool:
    """Memory-efficient, thread-safe singleton for GCP async clients with lazy initialization and cleanup."""

    _instance: Optional["ClientPool"] = None
    _lock = asyncio.Lock()

    def __init__(self) -> None:
        self._clients: Dict[str, Any] = {}
        self._client_types: Dict[str, Type[Any]] = {
            "assets": AssetServiceAsyncClient,
            "projects": ProjectsAsyncClient,
            "folders": FoldersAsyncClient,
            "orgs": OrganizationsAsyncClient,
            "publisher": PublisherAsyncClient,
            "subscriber": SubscriberAsyncClient,
        }

    @classmethod
    def instance(cls) -> "ClientPool":
        """Return the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_client(self, name: str) -> Any:
        """Get or lazily initialize a GCP client by name."""
        if name not in self._client_types:
            raise ValueError(f"Unknown client type: {name}")
        if name not in self._clients:
            async with self._lock:
                if name not in self._clients:
                    logger.debug(f"Creating {name} client")
                    self._clients[name] = self._client_types[name]()
        return self._clients[name]

    async def get_assets_client(self) -> AssetServiceAsyncClient:
        return await self.get_client("assets")

    async def get_projects_client(self) -> ProjectsAsyncClient:
        return await self.get_client("projects")

    async def get_folders_client(self) -> FoldersAsyncClient:
        return await self.get_client("folders")

    async def get_orgs_client(self) -> OrganizationsAsyncClient:
        return await self.get_client("orgs")

    async def get_publisher_client(self) -> PublisherAsyncClient:
        return await self.get_client("publisher")

    async def get_subscriber_client(self) -> SubscriberAsyncClient:
        return await self.get_client("subscriber")

    async def cleanup(self) -> None:
        """Clean up all clients by closing them."""
        async with self._lock:
            for name, client in self._clients.items():
                try:
                    close = getattr(client, "close", None)
                    if callable(close):
                        if asyncio.iscoroutinefunction(close):
                            await close()
                        else:
                            close()
                        logger.debug(f"Closed {name} client")
                except Exception as e:
                    logger.warning(f"Failed to close {name} client: {e}")
            self._clients.clear()


async def cleanup_all_client_pools() -> None:
    client_pool = ClientPool()
    await client_pool.cleanup()


client_pool = ClientPool()
