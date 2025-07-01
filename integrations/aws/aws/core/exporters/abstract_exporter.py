from abc import ABC, abstractmethod
from typing import Any, Optional, Self, AsyncGenerator
from aiobotocore.session import AioSession
from aws.core.options import SupportedServices


class AbstractResourceExporter(ABC):

    SERVICE_NAME: SupportedServices

    def __init__(self, session: AioSession, region: str) -> None:
        self.session = session
        self.region = region
        self._client: Optional[Any] = None

    async def __aenter__(self) -> Self:
        self._client = await self.session.create_client(
            service_name=self.SERVICE_NAME, region_name=self.region
        ).__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._client:
            await self._client.__aexit__(exc_type, exc, tb)

    @abstractmethod
    async def get_resource(self, options: Any) -> dict[str, Any]:
        """Fetch a single resource's detailed data by ID (e.g., ARN, URL, Name)."""
        ...

    @abstractmethod
    def get_paginated_resources(
        self, options: Any
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch paginated number of pages of resources."""
        ...
