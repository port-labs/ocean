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
    from integration import IssueResourceConfig


class ListIssueOptions(ListOptions["IssueResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "IssueResourceConfig"
    ) -> "ListIssueOptions":
        return cls()


class GetIssueOptions(GetOptions["IssueResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "IssueResourceConfig", *, resource_id: str
    ) -> "GetIssueOptions":
        return cls(resource_id=resource_id)


class IssueExporter(
    PaginatedExporter[ListIssueOptions], SingleResourceExporter[GetIssueOptions]
):
    async def get_paginated_resources(
        self, options: ListIssueOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info("Getting issues from Linear")
        async for issues in self._paginate_graphql_objects(
            LinearObject.ISSUES, page_size=options.page_size
        ):
            yield issues

    async def get_resource(self, options: GetIssueOptions) -> dict[str, Any]:
        logger.info(f"Querying single issue: {options.resource_id}")
        data = await execute_query_template(
            self.graphql,
            "GET_SINGLE_ISSUE",
            error_prefix=f"Could not fetch issue '{options.resource_id}'",
            issue_identifier=options.resource_id,
            base_query_fields=QUERIES[f"BASE_{LinearObject.ISSUES}_QUERY_FIELDS"],
        )
        return data["issue"]
