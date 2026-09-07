from typing import Any

from loguru import logger

from linear.client.constants import LinearObject
from linear.client.pagination import paginate_graphql_objects
from linear.client.templating import execute_query_template
from linear.core.exporters.base_exporter import LinearExporter
from linear.queries import QUERIES
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class DocumentExporter(LinearExporter):
    async def get_paginated_resources(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info("Getting documents from Linear")
        async for documents in paginate_graphql_objects(
            self.graphql, LinearObject.DOCUMENTS
        ):
            yield documents

    async def get_resource(self, document_id: str) -> dict[str, Any]:
        logger.info(f"Querying single document: {document_id}")
        data = await execute_query_template(
            self.graphql,
            "GET_SINGLE_DOCUMENT",
            error_prefix=f"Could not fetch document '{document_id}'",
            document_id=document_id,
            base_query_fields=QUERIES[f"BASE_{LinearObject.DOCUMENTS}_QUERY_FIELDS"],
        )
        return data["document"]
