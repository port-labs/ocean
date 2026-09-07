from typing import Any

from loguru import logger

from linear.client.constants import LinearObject
from linear.client.pagination import paginate_graphql_objects
from linear.client.templating import execute_query_template
from linear.core.exporters.base_exporter import LinearExporter
from linear.queries import QUERIES
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class IssueExporter(LinearExporter):
    async def get_paginated_resources(self) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info("Getting issues from Linear")
        async for issues in paginate_graphql_objects(self.graphql, LinearObject.ISSUES):
            yield issues

    async def get_resource(self, issue_identifier: str) -> dict[str, Any]:
        logger.info(f"Querying single issue: {issue_identifier}")
        data = await execute_query_template(
            self.graphql,
            "GET_SINGLE_ISSUE",
            error_prefix=f"Could not fetch issue '{issue_identifier}'",
            issue_identifier=issue_identifier,
            base_query_fields=QUERIES[f"BASE_{LinearObject.ISSUES}_QUERY_FIELDS"],
        )
        return data["issue"]
