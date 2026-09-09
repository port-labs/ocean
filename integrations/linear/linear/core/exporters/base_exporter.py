from abc import ABC
from typing import TYPE_CHECKING, Any, AsyncGenerator, ClassVar, Generic, TypeVar

import jinja2
from loguru import logger
from pydantic.v1 import BaseModel
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from linear.client import LinearClient
from linear.client.constants import (
    CONNECTION_KEYS,
    NODE_PAGINATION_OBJECTS,
    PAGE_SIZE,
    SINGLE_RESOURCE_CONFIG,
    LinearObject,
)
from linear.client.graphql import GraphqlClient
from linear.queries import QUERIES

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


GetOptionsT = TypeVar("GetOptionsT", bound=GetOptions[Any])


class LinearExporter(ABC):
    object_type: ClassVar[LinearObject]

    def __init__(self, client: LinearClient) -> None:
        self.client = client

    @property
    def graphql(self) -> GraphqlClient:
        return self.client.graphql


class PaginatedExporter(LinearExporter):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info(f"Getting {CONNECTION_KEYS[self.object_type]} from Linear")
        async for batch in self._paginate_graphql_objects(self.object_type):
            yield batch

    async def _paginate_graphql_objects(
        self,
        object_type: LinearObject,
        *,
        page_size: int = PAGE_SIZE,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        connection_key = CONNECTION_KEYS[object_type]
        has_next_page = True
        end_cursor: str | None = None

        while has_next_page:
            template = jinja2.Template(
                QUERIES[f"GET_{object_type}_PAGE"], enable_async=True
            )
            query = await template.render_async(
                page_size=page_size,
                after_cursor=f', after: "{end_cursor}"' if end_cursor else "",
                base_query_fields=(
                    QUERIES[f"BASE_{object_type}_QUERY_FIELDS"]
                    if f"BASE_{object_type}_QUERY_FIELDS" in QUERIES
                    else ""
                ),
            )
            logger.debug(f"{object_type} query: {query}")
            data = await self.graphql.execute(
                query,
            )
            connection = data[connection_key]
            if object_type in NODE_PAGINATION_OBJECTS:
                yield connection["nodes"]
            else:
                yield [edge["node"] for edge in connection["edges"]]
            has_next_page = connection["pageInfo"]["hasNextPage"]
            end_cursor = connection["pageInfo"]["endCursor"]


class SingleResourceExporter(LinearExporter, Generic[GetOptionsT]):
    async def get_resource(self, options: GetOptionsT) -> dict[str, Any]:
        config = SINGLE_RESOURCE_CONFIG[self.object_type]
        logger.info(f"Querying single {config.log_label}: {options.resource_id}")
        data = await self.graphql.execute_query_template(
            config.query_key,
            **{config.id_param: options.resource_id},
            base_query_fields=QUERIES.get(f"BASE_{self.object_type}_QUERY_FIELDS", ""),
        )
        return data[config.response_key]
