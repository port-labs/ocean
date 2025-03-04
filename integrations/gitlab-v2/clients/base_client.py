from typing import AsyncIterator, Any
from .graphql_client import GraphQLClient
from .rest_client import RestClient
from .auth_client import AuthClient


class GitLabClient:
    def __init__(self, base_url: str, token: str) -> None:
        auth_client = AuthClient(token)
        self.graphql = GraphQLClient(base_url, auth_client)
        self.rest = RestClient(base_url, auth_client)

    async def get_projects(self) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch all accessible projects using GraphQL.

        Note: GraphQL is preferred over REST for projects as it allows efficient
        fetching of extendable fields (like members, labels) in a single query
        when needed, avoiding multiple API calls.

        Returns:
            AsyncIterator yielding batches of project data
        """
        async for batch in self.graphql.get_resource("projects"):
            yield batch

    async def get_groups(self) -> AsyncIterator[list[dict[str, Any]]]:
        async for batch in self.rest.get_resource(
            "groups", params={"min_access_level": 30, "all_available": True}
        ):
            yield batch

    async def get_group_resource(
        self, group: dict[str, Any], resource_type: str
    ) -> AsyncIterator[list[dict[str, Any]]]:
        async for batch in self.rest.get_group_resource(group["id"], resource_type):
            yield batch
