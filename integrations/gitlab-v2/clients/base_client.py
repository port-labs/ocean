from typing import AsyncIterator, Any, AsyncGenerator
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

    async def get_groups(self) -> AsyncIterator[list[dict[str, Any]]]:
        try:
            async for groups_batch in self.rest.make_paginated_request(
                "groups",
                params={"min_access_level": 30, "all_available": True},
                page_size=100,
            ):
                logger.info(f"Processing batch of {len(groups_batch)} groups.")
                yield groups_batch

        except Exception as e:
            logger.error(f"Failed to fetch groups: {str(e)}")
            raise

    async def get_group_resource(
        self, group: dict, resource_type: str
    ) -> AsyncGenerator[list[dict], None]:
        async for batch in self.rest.get_group_resource(group["id"], resource_type):
            yield batch
