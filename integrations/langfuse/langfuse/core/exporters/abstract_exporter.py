from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any, Optional

from langfuse.clients.http.langfuse_client import LangfuseClient
from port_ocean.core.ocean_types import RAW_ITEM


class AbstractLangfuseExporter(ABC):
    def __init__(self, client: LangfuseClient) -> None:
        self.client = client

    @abstractmethod
    async def get_resource(self, options: Any) -> Optional[RAW_ITEM]: ...

    @abstractmethod
    async def get_paginated_resources(
        self, options: Any
    ) -> AsyncIterator[list[RAW_ITEM]]:
        if False:
            yield []
        raise NotImplementedError
