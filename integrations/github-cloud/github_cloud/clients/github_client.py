import asyncio
from functools import partial

from typing import Any, AsyncIterator, Callable, Optional, Awaitable, Union, Dict, List
from urllib.parse import quote

from loguru import logger
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)

from github_cloud.clients.rest_client import RestClient
from github_cloud.helpers.utils import parse_file_content
from port_ocean.utils.cache import cache_iterator_result

PARSEABLE_EXTENSIONS = (".json", ".yaml", ".yml")


class GitHubCloudClient:
    """Main GitHub Cloud client with high-level methods for Port Ocean integration."""

    def __init__(self, base_url: str, token: str) -> None:
        """
        Initialize the GitHub Cloud client.

        Args:
            base_url: GitHub Cloud API base URL
            token: GitHub Cloud access token
        """
        self.rest = RestClient(base_url, token)

    async def get_repository(self, repo_path: str) -> dict[str, Any]:
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
    ) -> dict[str, Any]:
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

    async def get_issue(self, repo_path: str, issue_number: int) -> dict[str, Any]:
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

    @cache_iterator_result()
    async def get_repositories(
        self,
        params: Optional[dict[str, Any]] = None,
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
        request_params = params or {}
        logger.info("Getting repositories for the authenticated user")
        async for repos_batch in self.rest.get_paginated_resource(
            "user/repos", params=request_params
        ):
                logger.info(f"Received batch with {len(repos_batch)} repositories")
                if include_languages:
                    enriched_batch = await self._enrich_batch(
                        repos_batch, self._enrich_repo_with_languages, max_concurrent
                    )
                    yield enriched_batch
                else:
                    yield repos_batch

    async def get_repository_resource(
        self,
        repos_batch: list[dict[str, Any]],
        resource_type: str,
        max_concurrent: int = 10,
        params: Optional[dict[str, Any]] = None,
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
                    params,
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
        Get a resource for multiple organizations.

        Args:
            orgs_batch: Batch of organizations
            resource_type: Resource type (e.g., teams, members)
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
        Get file content from a repository.

        Args:
            repo_path: Repository full name (owner/repo)
            file_path: Path to file in repository
            ref: Git reference (branch, tag, commit)

        Returns:
            File content as string or None if not found
        """
        try:
            response = await self.rest.send_api_request(
                "GET",
                f"repos/{repo_path}/contents/{file_path}",
                params={"ref": ref},
            )
            return response.get("content", "")
        except Exception as e:
            logger.error(f"Error getting file content: {e}")
            return None

    async def file_exists(
        self, repo_path: str, path: str, ref: str = "main"
    ) -> bool:
        """
        Check if a file exists in a repository.

        Args:
            repo_path: Repository full name (owner/repo)
            path: Path to file in repository
            ref: Git reference (branch, tag, commit)

        Returns:
            True if file exists, False otherwise
        """
        try:
            await self.rest.send_api_request(
                "GET",
                f"repos/{repo_path}/contents/{path}",
                params={"ref": ref},
            )
            return True
        except Exception:
            return False

    async def _process_file(
        self, file: dict[str, Any], context: str, skip_parsing: bool = False
        ) -> dict[str, Any]:
        """
        Process a file from GitHub Cloud.

        Args:
            file: File data from GitHub Cloud
            context: Context for logging
            skip_parsing: Whether to skip parsing file content

        Returns:
            Processed file data
        """
        try:
            content = file.get("content", "")
            if not content:
                return file

            if skip_parsing:
                return file

            file_path = file.get("path", "")
            if not file_path.lower().endswith(PARSEABLE_EXTENSIONS):
                return file

            parsed_content = parse_file_content(content, file_path)
            if parsed_content:
                file["parsed_content"] = parsed_content

            return file
        except Exception as e:
            logger.error(f"Error processing file in {context}: {e}")
            return file

    async def get_team_members(
        self, org_name: str, team_slug: str, include_bot_members: bool = False
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        Get team members.

        Args:
            org_name: Organization name
            team_slug: Team slug
            include_bot_members: Whether to include bot members

        Yields:
            Batches of team members
        """
        async for members_batch in self.rest.get_paginated_resource(
            f"orgs/{org_name}/teams/{team_slug}/members"
        ):
            if not include_bot_members:
                members_batch = [
                    member for member in members_batch
                    if not member.get("type") == "Bot"
                ]
            yield members_batch

    async def _enrich_repo_with_languages(self, repo: dict[str, Any]) -> dict[str, Any]:
        """
        Enrich repository with language data.

        Args:
            repo: Repository data

        Returns:
            Enriched repository data
        """
        try:
            languages = await self.rest.send_api_request(
                "GET", f"repos/{repo['full_name']}/languages"
            )
            repo["languages"] = languages
            return repo
        except Exception as e:
            logger.error(f"Error enriching repo with languages: {e}")
            return repo

    async def _enrich_batch(
        self,
        batch: list[dict[str, Any]],
        enrich_func: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        max_concurrent: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Enrich a batch of items.

        Args:
            batch: Batch of items
            enrich_func: Function to enrich items
            max_concurrent: Maximum concurrent requests

        Returns:
            Enriched batch
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = [
            self._enrich_item(item, enrich_func, semaphore)
            for item in batch
        ]
        return await asyncio.gather(*tasks)

    async def _enrich_item(
        self,
        item: dict[str, Any],
        enrich_func: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        semaphore: asyncio.Semaphore,
    ) -> dict[str, Any]:
        """
        Enrich a single item.

        Args:
            item: Item to enrich
            enrich_func: Function to enrich item
            semaphore: Semaphore for concurrency control

        Returns:
            Enriched item
        """
        async with semaphore:
            return await enrich_func(item)

    async def enrich_organization_with_members(
        self, org: dict[str, Any], team_slug: str, include_bot_members: bool
    ) -> dict[str, Any]:
        """
        Enrich organization with team members.

        Args:
            org: Organization data
            team_slug: Team slug
            include_bot_members: Whether to include bot members

        Returns:
            Enriched organization data
        """
        members = []
        async for members_batch in self.get_team_members(
            org["login"], team_slug, include_bot_members
        ):
            members.extend(members_batch)
        org["team_members"] = members
        return org

    async def get_issues(self, repo_name: str, state: str = "open") -> AsyncIterator[List[Dict[str, Any]]]:
        """
        Get all issues from a repository.

        Args:
            repo_name: Repository name in format 'owner/repo'
            state: Issue state (open, closed, or all)

        Returns:
            Async iterator yielding batches of issues
        """
        params = {"state": state}
        async for batch in self.rest.get_paginated_repo_resource(repo_name, "issues", params=params):
            yield batch
