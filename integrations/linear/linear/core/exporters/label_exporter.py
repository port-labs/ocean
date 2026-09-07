from typing import TYPE_CHECKING, Any

from loguru import logger

from linear.client.constants import LinearObject
from linear.client.templating import execute_query_template
from linear.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)
from linear.queries import QUERIES
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

if TYPE_CHECKING:
    from integration import LabelResourceConfig


class GetLabelOptions(GetOptions["LabelResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "LabelResourceConfig", *, resource_id: str
    ) -> "GetLabelOptions":
        return cls(resource_id=resource_id)


class LabelExporter(
    PaginatedExporter, SingleResourceExporter[GetLabelOptions]
):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info("Getting labels from Linear")
        async for labels in self._paginate_graphql_objects(LinearObject.LABELS):
            yield labels

    async def get_resource(self, options: GetLabelOptions) -> dict[str, Any]:
        logger.info(f"Querying single label: {options.resource_id}")
        data = await execute_query_template(
            self.graphql,
            "GET_SINGLE_LABEL",
            error_prefix=f"Could not fetch label '{options.resource_id}'",
            label_id=options.resource_id,
            base_query_fields=QUERIES[f"BASE_{LinearObject.LABELS}_QUERY_FIELDS"],
        )
        return data["issueLabel"]
