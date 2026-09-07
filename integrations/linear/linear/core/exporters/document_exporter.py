from typing import TYPE_CHECKING, Any

from loguru import logger

from linear.client.constants import LinearObject
from linear.client.templating import execute_query_template
from linear.core.exporters.base_exporter import (
    GetOptions,
    ListOptions,
    PaginatedExporter,
    SingleResourceExporter,
)
from linear.queries import QUERIES
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

if TYPE_CHECKING:
    from integration import DocumentResourceConfig


class ListDocumentOptions(ListOptions["DocumentResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "DocumentResourceConfig"
    ) -> "ListDocumentOptions":
        return cls()


class GetDocumentOptions(GetOptions["DocumentResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "DocumentResourceConfig", *, resource_id: str
    ) -> "GetDocumentOptions":
        return cls(resource_id=resource_id)


class DocumentExporter(
    PaginatedExporter[ListDocumentOptions],
    SingleResourceExporter[GetDocumentOptions],
):
    async def get_paginated_resources(
        self, options: ListDocumentOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info("Getting documents from Linear")
        async for documents in self._paginate_graphql_objects(
            LinearObject.DOCUMENTS, page_size=options.page_size
        ):
            yield documents

    async def get_resource(self, options: GetDocumentOptions) -> dict[str, Any]:
        logger.info(f"Querying single document: {options.resource_id}")
        data = await execute_query_template(
            self.graphql,
            "GET_SINGLE_DOCUMENT",
            error_prefix=f"Could not fetch document '{options.resource_id}'",
            document_id=options.resource_id,
            base_query_fields=QUERIES[f"BASE_{LinearObject.DOCUMENTS}_QUERY_FIELDS"],
        )
        return data["document"]
