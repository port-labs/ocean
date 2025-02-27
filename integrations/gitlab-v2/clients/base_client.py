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
        async for batch in self.graphql.get_resource("projects"):
            yield batch

    async def get_groups(self) -> AsyncIterator[list[dict[str, Any]]]:
        async for batch in self.rest.get_resource(
            "groups", params={"min_access_level": 30, "all_available": True}
        ):
            yield batch

    async def get_issues(self) -> AsyncIterator[list[dict[str, Any]]]:
        async for batch in self.rest.get_resource(
            "issues", params={"scope": "all", "state": "closed"}
        ):
            yield batch

    async def get_group_resource(
        self, group: dict, resource_type: str
    ) -> AsyncIterator[list[dict[str, Any]]]:
        async for batch in self.rest.get_group_resource(group["id"], resource_type):
            yield batch
