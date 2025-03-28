import asyncio
from functools import partial
from typing import Any, AsyncIterator, Callable, Optional

from loguru import logger
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)

from gitlab.clients.rest_client import RestClient


class GitLabClient:
    DEFAULT_MIN_ACCESS_LEVEL = 30
    DEFAULT_PARAMS = {
        "min_access_level": DEFAULT_MIN_ACCESS_LEVEL,
        "all_available": True,
    }

    def __init__(self, base_url: str, token: str) -> None:
        self.rest = RestClient(base_url, token, endpoint="api/v4")

    async def get_project(self, project_id: int) -> dict[str, Any]:
        return await self.rest.send_api_request(
            "GET", f"projects/{project_id}", params=self.DEFAULT_PARAMS
        )

    async def get_group(self, group_id: int) -> dict[str, Any]:
        return await self.rest.send_api_request(
            "GET", f"groups/{group_id}", params=self.DEFAULT_PARAMS
        )

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
                    enriched_batch, self.enrich_project_with_languages, max_concurrent
                )

            yield enriched_batch

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

    async def enrich_project_with_languages(
        self, project: dict[str, Any]
    ) -> AsyncIterator[list[dict[str, Any]]]:

        project_path = project.get("path_with_namespace", str(project["id"]))
        logger.debug(f"Enriching {project_path} with languages")
        languages = await self.rest.get_project_languages(project_path)
        logger.info(f"Fetched languages for {project_path}: {languages}")
        project["__languages"] = languages
        yield [project]

    async def get_groups(
        self, root_only: bool = False
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """Fetch all groups accessible to the user.

        Args:
            root_only: If True, only fetch root groups
        """

        async for batch in self.rest.get_paginated_resource(
            "groups", params=self.DEFAULT_PARAMS
        ):
            if root_only:
                yield [group for group in batch if group["parent_id"] is None]
            else:
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
