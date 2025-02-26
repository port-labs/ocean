from typing import AsyncIterator, Optional, Any
from .graphql_client import GraphQLClient
from .rest_client import RestClient
from .auth_client import AuthClient
from .queries import ProjectQueries, GroupQueries
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
        cursor = None

        while True:
            try:
                data = await self.graphql.execute_query(
                    str(GroupQueries.LIST),
                    variables={"cursor": cursor},
                )

                groups_data = data.get("groups", {})
                nodes = groups_data.get("nodes", [])

                if not nodes:
                    break

                yield nodes

                page_info = groups_data.get("pageInfo", {})
                if not page_info.get("hasNextPage", False):
                    break

                cursor = page_info.get("endCursor")

            except Exception as e:
                logger.error(f"Failed to fetch groups: {str(e)}")
                raise

    async def get_issues(self) -> AsyncIterator[list[dict[str, Any]]]:
        """Get all issues with pagination using REST API, The GraphQL API for issues is in experimental stage and is shaky."""
        try:
            params = {}

            async for issues_batch in self.rest.make_paginated_request(
                "issues", params=params
            ):
                logger.info(f"Received issue batch with {len(issues_batch)} issues")
                yield issues_batch

        except Exception as e:
            logger.error(f"Failed to fetch issues: {str(e)}")
            raise

    async def get_merge_requests(self) -> AsyncIterator[list[dict[str, Any]]]:
        """Get all merge requests with pagination using REST API. The GraphQL API for Merge Request is shaky."""
        try:
            params = {}

            async for merge_requests_batch in self.rest.make_paginated_request(
                "merge_requests", params=params
            ):
                logger.info(
                    f"Received merge request batch with {len(merge_requests_batch)} merge requests"
                )
                yield merge_requests_batch

        except Exception as e:
            logger.error(f"Failed to fetch merge requests: {str(e)}")
            raise
