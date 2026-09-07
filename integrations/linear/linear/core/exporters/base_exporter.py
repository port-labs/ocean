from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, AsyncGenerator, Generic, TypeVar

from pydantic.v1 import BaseModel
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from linear.client import LinearClient
from linear.client.constants import PAGE_SIZE, LinearObject
from linear.client.graphql import GraphqlClient
from linear.client.pagination import paginate_graphql_objects

if TYPE_CHECKING:
    from port_ocean.core.handlers.port_app_config.models import ResourceConfig

RC = TypeVar("RC", bound="ResourceConfig")


class GetOptions(BaseModel, Generic[RC]):
    """Base for single-resource-exporter options."""

    resource_id: str

    @classmethod
    def from_resource_config(
        cls, resource_config: RC, *, resource_id: str
    ) -> "GetOptions[RC]":
        raise NotImplementedError(f"{cls.__name__} must implement from_resource_config")


GetOptionsT = TypeVar("GetOptionsT")


class LinearExporter(ABC):
    def __init__(self, client: LinearClient) -> None:
        self.client = client

    @property
    def graphql(self) -> GraphqlClient:
        return self.client.graphql


class PaginatedExporter(LinearExporter):
    @abstractmethod
    def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE: ...

    async def _paginate_graphql_objects(
        self,
        object_type: LinearObject,
        *,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in paginate_graphql_objects(
            self.graphql, object_type, page_size=page_size
        ):
            yield batch


class SingleResourceExporter(LinearExporter, Generic[GetOptionsT]):
    @abstractmethod
    async def get_resource(self, options: GetOptionsT) -> dict[str, Any]: ...
