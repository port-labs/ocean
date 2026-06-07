from typing import TypeVar, Generic, Any, AsyncGenerator

from abc import ABC, abstractmethod

from pydantic import BaseModel
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.client import DatadogClient

MAX_PAGE_SIZE = 100


class ListOptions(BaseModel):
    """Base for all paginated-exporter options.

    Each subclass must implement from_resource_config(resource_config) so callers
    never need to know which ResourceConfig fields map to which option fields.
    """

    @classmethod
    def from_resource_config(cls, resource_config: Any) -> "ListOptions":
        raise NotImplementedError(f"{cls.__name__} must implement from_resource_config")


class GetOptions(BaseModel):
    """Base for all single-resource-exporter options.

    Subclasses must implement from_resource_config(resource_config, *, ...).
    resource_config is always first; the explicit resource identifier (e.g. id,
    resource_id, service_id) follows as a keyword-only argument since it doesn't
    live inside ResourceConfig and its name varies per resource type.
    """

    @classmethod
    def from_resource_config(cls, resource_config: Any, **kwargs: Any) -> "GetOptions":
        raise NotImplementedError(f"{cls.__name__} must implement from_resource_config")


ListOptionsT = TypeVar("ListOptionsT", bound=ListOptions)
GetOptionsT = TypeVar("GetOptionsT", bound=GetOptions)


class DatadogExporter(ABC):
    """Base class for all Datadog exporters, provides client access."""

    def __init__(self, client: DatadogClient) -> None:
        self.client = client


class PaginatedExporter(DatadogExporter, Generic[ListOptionsT]):
    """Mixin for exporters that support paginated resource listing."""

    @abstractmethod
    def get_paginated_resources(
        self, options: ListOptionsT
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


class SingleResourceExporter(DatadogExporter, Generic[GetOptionsT]):
    """Mixin for exporters that support single resource fetching."""

    @abstractmethod
    async def get_resource(self, options: GetOptionsT) -> dict[str, Any] | None: ...
