from typing import AsyncIterator, Optional, Any
from .graphql_client import GraphQLClient
from .rest_client import RestClient
from .auth_client import AuthClient
from .queries import ProjectQueries
from loguru import logger


class GitLabClient:
    def __init__(self, base_url: str, token: str) -> None:
        auth_client = AuthClient(token)
        self.graphql = GraphQLClient(base_url, auth_client)
        self.rest = RestClient(base_url, auth_client)

    async def get_projects(self) -> AsyncIterator[list[dict[str, Any]]]:
        """Get all projects with pagination."""
        cursor = None

        while True:
            try:
                data = await self.graphql.execute_query(
                    str(ProjectQueries.LIST),
                    variables={"cursor": cursor},
                )

                projects_data = data.get("projects", {})
                nodes = projects_data.get("nodes", [])

                if not nodes:
                    break

                yield nodes

                page_info = projects_data.get("pageInfo", {})
                if not page_info.get("hasNextPage", False):
                    break

                cursor = page_info.get("endCursor")

            except Exception as e:
                logger.error(f"Failed to fetch projects: {str(e)}")
                raise
