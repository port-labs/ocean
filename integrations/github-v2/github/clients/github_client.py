import os
import asyncio
import httpx
from functools import partial

import anyio
from typing import Any, AsyncIterator, Callable, Optional, Awaitable, Union, List, Dict
from urllib.parse import quote

from loguru import logger
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)
from port_ocean.utils.cache import cache_iterator_result

from github.clients.rest_client import RestClient


class GitHubClient:
    """Main GitHub client with high-level methods for Port Ocean integration."""

    def __init__(self, base_url: str, token: str) -> None:
        """
        Initialize the GitHub client.

        Args:
            base_url: GitHub API base URL
            token: GitHub access token
        """
        self.rest = RestClient(base_url, token)

    async def get_repository(self, repo_path: str) -> Optional[httpx.Response]:
        """
        Get a repository by full name.

        Args:
            repo_path: Repository full name (owner/repo)

        Returns:
            Repository data
        """
        encoded_path = quote(str(repo_path), safe="")
        return await self.rest.send_api_request("GET", f"repos/{encoded_path}")



    async def get_pull_request(
        self, repo_path: str, pull_request_number: int
    ) -> Optional[httpx.Response]:
        """
        Get a pull request by number.

        Args:
            repo_path: Repository full name (owner/repo)
            pull_request_number: Pull request number

        Returns:
            Pull request data
        """
        return await self.rest.send_api_request(
            "GET", f"repos/{repo_path}/pulls/{pull_request_number}"
        )

    async def get_issue(self, repo_path: str, issue_number: int) -> Optional[httpx.Response]:
        """
        Get an issue by number.

        Args:
            repo_path: Repository full name (owner/repo)
            issue_number: Issue number

        Returns:
            Issue data
        """
        return await self.rest.send_api_request(
            "GET", f"repos/{repo_path}/issues/{issue_number}"
        )

    async def get_organizations(
        self, params: Optional[dict[str, Any]] = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        Get organizations the token has access to.

        Args:
            params: Query parameters

        Yields:
            Batches of organizations
        """
        async for orgs_batch in self.rest.get_paginated_resource(
            "user/orgs", params=params
        ):
            yield orgs_batch


    async def get_repositories(
        self,
        max_concurrent: int = 10,
        include_languages: bool = False,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        Get repositories with optional enrichment.

        Args:
            params: Query parameters
            max_concurrent: Maximum concurrent requests for enrichment
            include_languages: Whether to include language data

        Yields:
            Batches of repositories
        """
        request_params =  {}
        logger.info("Getting repositories for the authenticated user")
        async for repos_batch in self.rest.get_paginated_resource(
            "user/repos", params=request_params
        ):
                logger.info(f"Received batch with {len(repos_batch)} repositories")
                yield repos_batch

    async def get_repository_resource(
        self,
        repos_batch: list[dict[str, Any]],
        resource_type: str,
        max_concurrent: int = 10,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        Get a resource for multiple repositories.

        Args:
            repos_batch: Batch of repositories
            resource_type: Resource type (e.g., issues, pulls)
            max_concurrent: Maximum concurrent requests
            params: Query parameters

        Yields:
            Batches of resources
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = [
            semaphore_async_iterator(
                semaphore,
                partial(
                    self.rest.get_paginated_repo_resource,
                    repo["full_name"],
                    resource_type,
                ),
            )
            for repo in repos_batch
        ]

        async for batch in stream_async_iterators_tasks(*tasks):
            if batch:
                yield batch

    async def get_organization_resource(
        self,
        orgs_batch: list[dict[str, Any]],
        resource_type: str,
        max_concurrent: int = 10,
        params: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        Get resources for multiple organizations.

        Args:
            orgs_batch: Batch of organizations
            resource_type: Resource type (e.g., repos, teams)
            max_concurrent: Maximum concurrent requests
            params: Query parameters

        Yields:
            Batches of resources
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = [
            semaphore_async_iterator(
                semaphore,
                partial(
                    self.rest.get_paginated_org_resource,
                    org["login"],
                    resource_type,
                    params,
                ),
            )
            for org in orgs_batch
        ]

        async for batch in stream_async_iterators_tasks(*tasks):
            if batch:
                yield batch

    async def get_file_content(
        self, repo_path: str, file_path: str, ref: str = "main"
    ) -> Optional[str]:
        """
        Get content of a file from a repository.

        Args:
            repo_path: Repository full name (owner/repo)
            file_path: Path to file in the repository
            ref: Git reference (branch, tag, commit)

        Returns:
            File content as string or None if not found
        """
        return await self.rest.get_file_content(repo_path, file_path, ref)
