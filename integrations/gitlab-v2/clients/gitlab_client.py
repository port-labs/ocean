from typing import Any, AsyncIterator, Optional
from loguru import logger

from .graphql_client import GraphQLClient
from .rest_client import RestClient
import urllib.parse
from .utils import convert_glob_to_gitlab_patterns, parse_file_content
import anyio
import asyncio
from port_ocean.utils.async_iterators import (
    stream_async_iterators_tasks,
    semaphore_async_iterator,
)
from functools import partial


class GitLabClient:
    """Async client for interacting with GitLab API using both GraphQL and REST endpoints."""

    DEFAULT_MIN_ACCESS_LEVEL = 30

    def __init__(self, base_url: str, token: str) -> None:

        self.graphql = GraphQLClient(base_url, token, endpoint="api/graphql")
        self.rest = RestClient(base_url, token, endpoint="api/v4")

    async def get_projects(
        self, params: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch all accessible projects using GraphQL.
        Note: GraphQL is preferred over REST for projects as it allows efficient
        fetching of extendable fields (like members, labels, files) in a single query
        when needed, avoiding multiple API calls.
        """
        async for projects_batch, field_iterators in self.graphql.get_resource(
            "projects", params
        ):
            if projects_batch:
                yield projects_batch

            async for updated_batch in self.graphql._process_nested_fields(
                projects_batch, field_iterators
            ):
                yield updated_batch

    async def get_groups(self) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch all groups accessible to the user."""
        async for batch in self.rest.get_resource(
            "groups",
            params={
                "min_access_level": self.DEFAULT_MIN_ACCESS_LEVEL,
                "all_available": True,
            },
        ):
            yield batch

    async def get_group_resource(
        self,
        groups_batch: list[dict[str, Any]],
        resource_type: str,
        max_concurrent: int = 10,
    ) -> AsyncIterator[list[dict[str, Any]]]:

        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = [
            semaphore_async_iterator(
                semaphore, partial(self._process_single_group, group, resource_type)
            )
            for group in groups_batch
        ]

        async for batch in stream_async_iterators_tasks(*tasks):
            if batch:
                yield batch

    async def _process_single_group(
        self,
        group: dict[str, Any],
        resource_type: str,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        group_id = group["id"]

        logger.debug(f"Starting fetch for {resource_type} in group {group_id}")
        async for resource_batch in self.rest.get_group_resource(
            group_id, resource_type
        ):
            if resource_batch:
                logger.info(
                    f"Fetched {len(resource_batch)} {resource_type} for group {group_id}"
                )
                yield resource_batch

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

    async def process_file(
        self,
        file: dict[str, Any],
        context: str,
    ) -> dict[str, Any]:
        """Fetch full file content and parse it."""
        file_path = file["path"]
        project_id = file["project_id"]
        ref = file.get("ref", "main")

        full_content = await self.get_file_content(project_id, file_path, ref)
        if full_content is not None:
            try:
                file["content"] = await anyio.to_thread.run_sync(
                    parse_file_content, full_content, file_path, context
                )
            except Exception as e:
                logger.error(f"Failed to parse {file_path} in {context}: {str(e)}")
                file["parsed_data"] = None
        else:
            file["content"] = None
        return file

    async def _process_batch(
        self,
        batch: list[dict[str, Any]],
        context: str,
    ) -> AsyncIterator[dict[str, Any]]:
        PARSEABLE_EXTENSIONS = (".json", ".yaml", ".yml")

        tasks = [
            (
                self.process_file(file, context)
                if file.get("path", "").endswith(PARSEABLE_EXTENSIONS)
                else asyncio.create_task(asyncio.sleep(0, result=file))
            )
            for file in batch
        ]

        # Process all files through as_completed
        for completed in asyncio.as_completed(tasks):
            yield await completed

    async def _search_in_repository(
        self,
        repo: str,
        patterns: list[str],
    ) -> AsyncIterator[list[dict[str, Any]]]:
        params = {"scope": "blobs", "search_type": "advanced"}
        for pattern in patterns:
            params["search"] = f"path:{pattern}"
            try:
                async for batch in self.get_project_resource(repo, "search", params):
                    if batch:
                        processed_batch = []
                        async for processed_file in self._process_batch(batch, repo):
                            processed_batch.append(processed_file)
                        if processed_batch:
                            yield processed_batch
            except Exception as e:
                logger.error(f"Error searching in {repo}: {str(e)}")

    async def _search_in_group(
        self,
        group: dict[str, Any],
        patterns: list[str],
    ) -> AsyncIterator[list[dict[str, Any]]]:
        group_context = group.get("name", str(group["id"]))
        params = {"scope": "blobs", "search_type": "advanced"}
        for pattern in patterns:
            params["search"] = f"path:{pattern}"
            group_id = group["id"]
            try:
                async for batch in self.rest.get_group_resource(group_id, "search", params):
                    logger.info(f"Received search batch for {group_context}")
                    if batch:
                        processed_batch = []
                        async for processed_file in self._process_batch(
                            batch, group_context
                        ):
                            processed_batch.append(processed_file)
                        if processed_batch:
                            yield processed_batch
            except Exception as e:
                logger.error(f"Error searching in {group_context}: {str(e)}")

    async def search_files(
            self,
            path_pattern: str,
            repositories: Optional[list[str]] = None,
            max_concurrent: int = 10,
        ) -> AsyncIterator[list[dict[str, Any]]]:
            logger.info(f"Searching for files matching pattern: '{path_pattern}'")
            patterns = convert_glob_to_gitlab_patterns(path_pattern)

            if repositories:
                logger.info(f"Searching in {len(repositories)} specific repositories")
                for repo in repositories:
                    logger.debug(f"Searching repo '{repo}' for pattern '{path_pattern}'")
                    async for batch in self._search_in_repository(repo, patterns):
                        yield batch
            else:
                logger.info("Searching across all accessible groups")
                async for groups in self.get_groups():
                    logger.debug(f"Processing batch of {len(groups)} groups")
                    semaphore = asyncio.Semaphore(max_concurrent)
                    tasks = [
                        semaphore_async_iterator(
                            semaphore, partial(self._search_in_group, group, patterns)
                        )
                        for group in groups
                    ]
                    async for batch in stream_async_iterators_tasks(*tasks):
                        yield batch
                        
    async def get_file_content(
        self, project_id: str, file_path: str, ref: str = "main"
    ) -> Optional[str]:
        return await self.rest.get_file_content(project_id, file_path, ref)
