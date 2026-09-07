from typing import Any

from loguru import logger

from linear.client.constants import LinearObject
from linear.client.pagination import paginate_graphql_objects
from linear.client.templating import execute_query_template
from linear.core.exporters.base_exporter import LinearExporter
from linear.queries import QUERIES
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class LabelExporter(LinearExporter):
    async def get_paginated_resources(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info("Getting labels from Linear")
        async for labels in paginate_graphql_objects(self.graphql, LinearObject.LABELS):
            yield labels

    async def get_resource(self, label_id: str) -> dict[str, Any]:
        logger.info(f"Querying single label: {label_id}")
        data = await execute_query_template(
            self.graphql,
            "GET_SINGLE_LABEL",
            error_prefix=f"Could not fetch label '{label_id}'",
            label_id=label_id,
            base_query_fields=QUERIES[f"BASE_{LinearObject.LABELS}_QUERY_FIELDS"],
        )
        return data["issueLabel"]
