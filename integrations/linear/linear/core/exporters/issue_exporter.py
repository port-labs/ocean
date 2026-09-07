from typing import TYPE_CHECKING, Any

from loguru import logger

from linear.client.constants import LinearObject
from linear.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)
from linear.queries import QUERIES
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

if TYPE_CHECKING:
    from integration import IssueResourceConfig


class GetIssueOptions(GetOptions["IssueResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "IssueResourceConfig", *, resource_id: str
    ) -> "GetIssueOptions":
        return cls(resource_id=resource_id)


class IssueExporter(PaginatedExporter, SingleResourceExporter[GetIssueOptions]):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info("Getting issues from Linear")
        async for issues in self._paginate_graphql_objects(LinearObject.ISSUES):
            yield issues

    async def get_resource(self, options: GetIssueOptions) -> dict[str, Any]:
        logger.info(f"Querying single issue: {options.resource_id}")
        data = await self.graphql.execute_query_template(
            "GET_SINGLE_ISSUE",
            issue_identifier=options.resource_id,
            base_query_fields=QUERIES[f"BASE_{LinearObject.ISSUES}_QUERY_FIELDS"],
        )
        return data["issue"]
