import asyncio
from functools import partial
from typing import Any, AsyncIterator, Callable, Optional

import anyio
from loguru import logger
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)
from urllib.parse import quote

from clients.rest_client import RestClient
from clients.utils import parse_file_content

PARSEABLE_EXTENSIONS = (".json", ".yaml", ".yml")


class GitLabClient:
    DEFAULT_MIN_ACCESS_LEVEL = 30
    DEFAULT_PARAMS = {
        "min_access_level": DEFAULT_MIN_ACCESS_LEVEL,
        "all_available": True,
    }

    def __init__(self, base_url: str, token: str) -> None:
        self.rest = RestClient(base_url, token, endpoint="api/v4")

    # Public: Project Methods
    async def get_project(self, project_path: str) -> dict[str, Any]:
        encoded_path = quote(project_path, safe="")
        path = f"projects/{encoded_path}"
        project_data = await self.rest.get_resource(path)
        return project_data

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

    async def get_groups(self) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch all groups accessible to the user."""
        async for batch in self.rest.get_paginated_resource(
            "groups", params=self.DEFAULT_PARAMS
        ):
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
                semaphore, partial(self._process_single_group, group, resource_type)
            )
            for group in groups_batch
        ]

        async for batch in stream_async_iterators_tasks(*tasks):
            if batch:
                yield batch

    async def get_file_content(
        self, project_id: str, file_path: str, ref: str = "main"
    ) -> Optional[str]:
        return await self.rest.get_file_content(project_id, file_path, ref)

    async def file_exists(self, project_id: str, scope: str, query: str) -> bool:
        params = {"scope": scope, "search": query}
        params = {"scope": scope, "search": query}
        encoded_project_path = quote(project_id, safe="")
        path = f"projects/{encoded_project_path}/search"
        response = await self.rest.get_resource(path, params=params)
        return bool(response)

    async def search_files(
        self,
        scope: str,
        query: str,
        repositories: Optional[list[str]] = None,
        max_concurrent: int = 10,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Search for files in repositories or groups using a scope and query, returning files with content."""
        logger.info(f"Searching for files with scope '{scope}' and query '{query}'")
        semaphore = asyncio.Semaphore(max_concurrent)

        if repositories:
            logger.info(f"Searching in {len(repositories)} repositories")
            for repo in repositories:
                logger.debug(f"Searching repo '{repo}' for query '{query}'")
                async for batch in self._search_in_repository(repo, scope, query):
                    yield batch
        else:
            logger.info("Searching across all accessible groups")
            async for groups in self.get_groups():
                logger.debug(f"Processing batch of {len(groups)} groups")
                tasks = [
                    semaphore_async_iterator(
                        semaphore,
                        partial(self._search_in_group, group, scope, query),
                    )
                    for group in groups
                ]
                async for batch in stream_async_iterators_tasks(*tasks):
                    yield batch

    async def get_repository_tree(
        self,
        project: dict[str, Any],
        path: str,
        ref: str = "main",
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch repository tree (folders only) for a project."""
        project_path = project["path_with_namespace"]
        params = {"ref": ref, "path": path, "recursive": True, "per_page": 100}
        async for batch in self.rest.get_paginated_project_resource(
            project_path, "repository/tree", params
        ):
            if folders_batch := [item for item in batch if item["type"] == "tree"]:
                yield [
                    {"folder": folder, "repo": project, "__branch": ref}
                    for folder in folders_batch
                ]

    async def search_folders(
        self, path: str, repos: list[str], branch: Optional[str] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Search for folders in specified repositories only."""
        for repo in repos:
            project = await self.get_project(repo)
            if project:
                effective_branch = branch or project["default_branch"]
                async for folders_batch in self.get_repository_tree(
                    project, path, effective_branch
                ):
                    if folders_batch:
                        yield folders_batch

    # Helpers: Enrichment
    async def _enrich_batch(
        self,
        batch: list[dict[str, Any]],
        enrich_func: Callable[[dict[str, Any]], AsyncIterator[list[dict[str, Any]]]],
        max_concurrent: int,
    ) -> list[dict[str, Any]]:
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = [
            semaphore_async_iterator(semaphore, partial(enrich_func, project))
            for project in batch
        ]
        enriched_projects = []
        async for enriched_batch in stream_async_iterators_tasks(*tasks):
            enriched_projects.extend(enriched_batch)
        return enriched_projects

    async def _enrich_project_with_languages(
        self, project: dict[str, Any]
    ) -> AsyncIterator[list[dict[str, Any]]]:
        project_path = project.get("path_with_namespace", str(project["id"]))
        logger.debug(f"Enriching {project_path} with languages")
        languages = await self.rest.get_project_languages(project_path)
        logger.info(f"Fetched languages for {project_path}: {languages}")
        project["__languages"] = languages
        yield [project]

    async def _process_single_group(
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

    async def _process_file(self, file: dict[str, Any], context: str) -> dict[str, Any]:
        """Fetch full file content and parse it."""
        file_path = file["path"]
        project_id = str(file["project_id"])
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
        self, batch: list[dict[str, Any]], context: str
    ) -> list[dict[str, Any]]:
        """Process a batch of files concurrently and return the full result."""
        tasks = [
            (
                self._process_file(file, context)
                if file.get("path", "").endswith(PARSEABLE_EXTENSIONS)
                else asyncio.sleep(0, result=file)
            )
            for file in batch
        ]
        return await asyncio.gather(*tasks)

    async def _search_in_repository(
        self,
        repo: str,
        scope: str,
        query: str,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Search files in a repository using a scope and query."""
        logger.debug(
            f"Searching repo '{repo}' for query '{query}' with scope '{scope}'"
        )
        params = {"scope": scope, "search": query}
        encoded_repo = quote(repo, safe="")
        path = f"projects/{encoded_repo}/search"
        async for batch in self.rest.get_paginated_resource(path, params=params):
            if batch:
                processed_batch = await self._process_batch(batch, repo)
                if processed_batch:
                    yield processed_batch

    async def _search_in_group(
        self,
        group: dict[str, Any],
        scope: str,
        query: str,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Search files in a group using a scope and query."""
        group_context = group.get("name", str(group["id"]))
        group_id = group["id"]
        params = {"scope": scope, "search": query}
        logger.debug(f"Searching group '{group_context}' for query '{query}'")
        async for batch in self.rest.get_paginated_group_resource(
            group_id, "search", params
        ):
            if batch:
                processed_batch = await self._process_batch(batch, group_context)
                if processed_batch:
                    yield processed_batch
