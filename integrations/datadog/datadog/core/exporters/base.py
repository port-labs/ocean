from typing import TypeVar, Generic, Any, AsyncGenerator

from abc import ABC, abstractmethod

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.client import DatadogClient, MAX_PAGE_SIZE

OptionsT = TypeVar("OptionsT")


class DatadogExporter(ABC):
    """Base class for all Datadog exporters, provides client access."""

    def __init__(self, client: DatadogClient) -> None:
        self.client = client


class PaginatedExporter(DatadogExporter, Generic[OptionsT]):
    """Mixin for exporters that support paginated resource listing."""

    @abstractmethod
    def get_paginated_resources(
        self, options: OptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE: ...

    async def _paginate_by_page_param(
        self,
        url: str,
        *,
        data_key: str | None = "data",
        page_param: str = "page[number]",
        size_param: str = "page[size]",
        page_size: int = MAX_PAGE_SIZE,
        extra_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Page-number based pagination. Increments page until empty response."""
        page = 0
        while True:
            params: dict[str, Any] = {
                page_param: page,
                size_param: page_size,
                **(extra_params or {}),
            }
            result = await self.client.send_api_request(url, params=params)

            items = result if data_key is None else result.get(data_key, [])
            if not items:
                break

            yield items
            page += 1

    async def _paginate_by_offset(
        self,
        url: str,
        *,
        data_key: str | None = "data",
        offset_param: str = "offset",
        size_param: str = "limit",
        page_size: int = MAX_PAGE_SIZE,
        extra_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Offset-based pagination. Increments offset by page_size until empty."""
        offset = 0
        while True:
            params: dict[str, Any] = {
                offset_param: offset,
                size_param: page_size,
                **(extra_params or {}),
            }
            result = await self.client.send_api_request(url, params=params)

            items = result if data_key is None else result.get(data_key, [])
            if not items:
                break

            yield items
            offset += page_size

    @staticmethod
    def _chunk_items(
        items: list[dict[str, Any]], chunk_size: int = MAX_PAGE_SIZE
    ) -> list[list[dict[str, Any]]]:
        """Split a flat list into chunks for yielding as pages."""
        return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


class SingleResourceExporter(DatadogExporter, Generic[OptionsT]):
    """Mixin for exporters that support single resource fetching."""

    @abstractmethod
    async def get_resource(self, options: OptionsT) -> dict[str, Any] | None: ...
