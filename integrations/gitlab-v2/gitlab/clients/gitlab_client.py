import asyncio
from functools import partial
from typing import Any, AsyncIterator, Callable, Optional, Awaitable

import anyio
from loguru import logger
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)
from urllib.parse import quote

from gitlab.helpers.utils import parse_file_content

from gitlab.clients.rest_client import RestClient

PARSEABLE_EXTENSIONS = (".json", ".yaml", ".yml")


class GitLabClient:
    DEFAULT_MIN_ACCESS_LEVEL = 30
    DEFAULT_PARAMS = {
        "min_access_level": DEFAULT_MIN_ACCESS_LEVEL,  # Minimum access level to fetch groups
        "all_available": True,  # Fetch all groups accessible to the user
    }

    def __init__(self, base_url: str, token: str) -> None:
        self.rest = RestClient(base_url, token, endpoint="api/v4")

    async def get_project(self, project_path: str | int) -> dict[str, Any]:
        encoded_path = quote(str(project_path), safe="")
        return await self.rest.send_api_request("GET", f"projects/{encoded_path}")

    async def get_group(self, group_id: int) -> dict[str, Any]:
        return await self.rest.send_api_request("GET", f"groups/{group_id}")

    async def get_merge_request(
        self, project_id: int, merge_request_id: int
    ) -> dict[str, Any]:
        return await self.rest.send_api_request(
            "GET", f"projects/{project_id}/merge_requests/{merge_request_id}"
        )

    async def get_issue(self, project_id: int, issue_id: int) -> dict[str, Any]:
        return await self.rest.send_api_request(
            "GET", f"projects/{project_id}/issues/{issue_id}"
        )

    async def get_projects(
        self,
        params: Optional[dict[str, Any]] = None,
        max_concurrent: int = 10,
        include_languages: bool = False,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch projects and optionally enrich with languages and/or labels."""
        request_params = self.DEFAULT_PARAMS | (params or {})
        async for projects_batch in self.rest.get_paginated_resource(
            "projects", params=request_params
        ):
            logger.info(f"Received batch with {len(projects_batch)} projects")
            enriched_batch = projects_batch

            if include_languages:
                enriched_batch = await self._enrich_batch(
                    enriched_batch, self._enrich_project_with_languages, max_concurrent
                )

            yield enriched_batch

    async def get_groups(
        self, top_level_only: bool = False
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch all groups accessible to the user.

        Args:
            top_level_only: If True, only fetch root groups
        """
        params = {**self.DEFAULT_PARAMS, "top_level_only": top_level_only}
        async for batch in self.rest.get_paginated_resource("groups", params=params):
            yield batch

    async def get_groups_resource(
        self,
        groups_batch: list[dict[str, Any]],
        resource_type: str,
        max_concurrent: int = 10,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = [
            semaphore_async_iterator(
                semaphore, partial(self._get_group_resource, group, resource_type)
            )
            for group in groups_batch
        ]

        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch

    async def get_file_content(
        self, project_id: str, file_path: str, ref: str
    ) -> Optional[str]:
        return await self.rest.get_file_content(project_id, file_path, ref)

    async def file_exists(self, project_id: str, scope: str, query: str) -> bool:
        params = {"scope": scope, "search": query}
        encoded_project_path = quote(project_id, safe="")
        path = f"projects/{encoded_project_path}/search"
        response = await self.rest.send_api_request("GET", path, params=params)
        return bool(response)

    async def search_files(
        self,
        scope: str,
        path: str,
        repositories: list[str] | None = None,
        skip_parsing: bool = False,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        search_query = f"path:{path}"
        logger.info(f"Starting file search with path pattern: '{path}'")

        if repositories:
            logger.info(f"Searching across {len(repositories)} specific repositories")
            for repo in repositories:
                logger.debug(f"Processing repository: {repo}")
                async for batch in self._search_files_in_repository(
                    repo, scope, search_query, skip_parsing
                ):
                    yield batch
        else:
            logger.info("Searching across all top-level groups")
            async for groups_batch in self.get_groups(top_level_only=True):
                logger.debug(f"Processing batch of {len(groups_batch)} groups")
                for group in groups_batch:
                    group_id = str(group["id"])
                    async for batch in self._search_files_in_group(
                        group_id, scope, search_query, skip_parsing
                    ):
                        yield batch

    async def get_repository_tree(
        self,
        project: dict[str, Any],
        path: str,
        ref: str = "main",
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch repository tree (folders only) for a project."""
        project_path = project["path_with_namespace"]
        params = {"ref": ref, "path": path, "recursive": False}
        async for batch in self.rest.get_paginated_project_resource(
            project_path, "repository/tree", params
        ):
            if folders_batch := [item for item in batch if item["type"] == "tree"]:
                yield [
                    {"folder": folder, "repo": project, "__branch": ref}
                    for folder in folders_batch
                ]

    async def get_repository_folders(
        self, path: str, repository: str, branch: Optional[str] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Search for folders in specified repositories only."""
        project = await self.get_project(repository)
        if project:
            effective_branch = branch or project["default_branch"]
            async for folders_batch in self.get_repository_tree(
                project, path, effective_branch
            ):
                yield folders_batch

    async def _enrich_batch(
        self,
        batch: list[dict[str, Any]],
        enrich_func: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        max_concurrent: int,
    ) -> list[dict[str, Any]]:
        semaphore = asyncio.Semaphore(max_concurrent)

        tasks = [
            self._enrich_project(project, enrich_func, semaphore) for project in batch
        ]

        return await asyncio.gather(*tasks)

    async def _enrich_project(
        self,
        project: dict[str, Any],
        enrich_func: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        semaphore: asyncio.Semaphore,
    ) -> dict[str, Any]:
        async with semaphore:
            return await enrich_func(project)

    async def _enrich_project_with_languages(
        self, project: dict[str, Any]
    ) -> dict[str, Any]:
        project_path = project.get("path_with_namespace", str(project["id"]))
        logger.debug(f"Enriching {project_path} with languages")
        languages = await self.rest.get_project_languages(project_path)
        logger.info(f"Fetched languages for {project_path}: {languages}")
        project["__languages"] = languages
        return project

    async def _get_group_resource(
        self,
        group: dict[str, Any],
        resource_type: str,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        group_id = group["id"]

        logger.debug(f"Starting fetch for {resource_type} in group {group_id}")
        async for resource_batch in self.rest.get_paginated_group_resource(
            group_id, resource_type
        ):
            if resource_batch:
                logger.info(
                    f"Fetched {len(resource_batch)} {resource_type} for group {group_id}"
                )
                yield resource_batch

    async def _process_file(
        self, file: dict[str, Any], context: str, skip_parsing: bool = False
    ) -> dict[str, Any]:
        file_path = file.get("path", "")
        project_id = str(file["project_id"])
        ref = file.get("ref", "main")

        file["content"] = await self.get_file_content(project_id, file_path, ref)

        if (
            not skip_parsing
            and file["content"] is not None
            and file_path.endswith(PARSEABLE_EXTENSIONS)
        ):
            file["content"] = await anyio.to_thread.run_sync(
                parse_file_content, file["content"], file_path, context
            )
        return file

    async def _process_file_batch(
        self,
        batch: list[dict[str, Any]],
        context: str,
        skip_parsing: bool = False,
    ) -> list[dict[str, Any]]:
        """Process a batch of files concurrently and return the full result."""
        tasks = [self._process_file(file, context, skip_parsing) for file in batch]
        return await asyncio.gather(*tasks)

    async def _search_files_in_repository(
        self,
        repo: str,
        scope: str,
        query: str,
        skip_parsing: bool = False,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        logger.debug(
            f"Starting search in repository '{repo}' for query '{query}' with scope '{scope}'"
        )
        params = {"scope": scope, "search": query}
        encoded_repo = quote(repo, safe="")
        path = f"projects/{encoded_repo}/search"

        async for file_batch in self.rest.get_paginated_resource(path, params=params):
            logger.debug(f"Found {len(file_batch)} files in '{repo}'")
            processed_batch = await self._process_file_batch(
                file_batch, repo, skip_parsing
            )
            if processed_batch:
                yield processed_batch

    async def _search_files_in_group(
        self,
        group_id: str,
        scope: str,
        query: str,
        skip_parsing: bool = False,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        logger.debug(
            f"Starting search in group '{group_id}' for query '{query}' with scope '{scope}'"
        )
        params = {"scope": scope, "search": query}
        encoded_group = quote(group_id, safe="")
        path = f"groups/{encoded_group}/search"

        async for file_batch in self.rest.get_paginated_resource(path, params=params):
            logger.debug(f"Found {len(file_batch)} files in group '{group_id}'")
            processed_batch = await self._process_file_batch(
                file_batch, group_id, skip_parsing
            )
            if processed_batch:
                yield processed_batch
