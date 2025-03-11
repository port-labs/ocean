from typing import Any, AsyncIterator, Optional

from .auth_client import AuthClient
from .graphql_client import GraphQLClient
from .rest_client import RestClient
from loguru import logger
import urllib.parse
from .utils import convert_glob_to_gitlab_patterns, parse_file_content
import anyio


class GitLabClient:

    def __init__(self, base_url: str, token: str) -> None:
        auth_client = AuthClient(token)
        self.graphql = GraphQLClient(base_url, auth_client)
        self.rest = RestClient(base_url, auth_client)

    async def get_projects(
        self, params: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch all accessible projects using GraphQL.

        Note: GraphQL is preferred over REST for projects as it allows efficient
        fetching of extendable fields (like members, labels) in a single query
        when needed, avoiding multiple API calls.

        Args:
            params: Optional params to pass to the GraphQL query

        Returns:
            AsyncIterator yielding batches of project data
        """
        async for batch in self.graphql.get_resource("projects", params=params):
            yield batch

    async def get_groups(self) -> AsyncIterator[list[dict[str, Any]]]:
        async for batch in self.rest.get_resource(
            "groups", params={"min_access_level": 30, "all_available": True}
        ):
            yield batch

    async def get_group_resource(
        self,
        group: dict[str, Any],
        resource_type: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        async for batch in self.rest.get_group_resource(
            group["id"], resource_type, params
        ):
            yield batch

    async def get_project_resource(
        self,
        project_path: str,
        resource_type: str,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        encoded_project_path = urllib.parse.quote(project_path, safe="")
        async for batch in self.rest.get_project_resource(
            encoded_project_path, resource_type, params
        ):
            yield batch

    async def _process_batch(
        self,
        batch: list[dict[str, Any]],
        context: str,
    ) -> list[dict[str, Any]]:
        PARSEABLE_EXTENSIONS = (".json", ".yaml", ".yml")

        for file in batch:
            file_path = file.get("path", "")
            if file_path.endswith(PARSEABLE_EXTENSIONS):
                try:
                    file["data"] = await anyio.to_thread.run_sync(
                        parse_file_content, file.get("data", ""), file_path, context
                    )
                except Exception as e:
                    logger.error(f"Failed to parse {file_path} in {context}: {str(e)}")
        return batch

    async def _search_in_repository(
        self,
        repo: str,
        patterns: list[str],
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Search for files in a specific repository."""
        params = {"scope": "blobs", "search_type": "advanced"}
        for pattern in patterns:
            params["search"] = f"path:{pattern}"
            try:
                async for batch in self.get_project_resource(repo, "search", params):
                    if batch:
                        yield await self._process_batch(batch, repo)
            except Exception as e:
                logger.error(f"Error searching in {repo}: {str(e)}")

    async def _search_in_group(
        self,
        group: dict[str, Any],
        patterns: list[str],
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Search for files in a specific group."""
        group_context = group.get("name", str(group["id"]))
        params = {"scope": "blobs", "search_type": "advanced"}
        for pattern in patterns:
            params["search"] = f"path:{pattern}"
            try:
                async for batch in self.get_group_resource(group, "search", params):
                    if batch:
                        yield await self._process_batch(batch, group_context)
            except Exception as e:
                logger.error(f"Error searching in {group_context}: {str(e)}")

    async def search_files(
        self,
        path_pattern: str,
        repositories: Optional[list[str]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        Search for files matching a path pattern in GitLab repositories or groups.
        Automatically parses content for json, yaml, and yml files.
        """
        logger.info(f"Searching for files matching pattern: '{path_pattern}'")
        patterns = convert_glob_to_gitlab_patterns(path_pattern)

        if repositories:
            logger.info(f"Searching in {len(repositories)} specific repositories")
            for repo in repositories:
                async for batch in self._search_in_repository(repo, patterns):
                    yield batch
        else:
            logger.info("Searching across all accessible groups")
            async for groups in self.get_groups():
                for group in groups:
                    async for batch in self._search_in_group(group, patterns):
                        yield batch

    async def get_file_content(
        self, project_id: str, file_path: str, ref: str = "main"
    ) -> Optional[str]:
        return await self.rest.get_file_content(project_id, file_path, ref)
