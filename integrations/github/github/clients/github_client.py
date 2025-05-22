import asyncio
import json
import yaml
from functools import partial

import anyio
from typing import Any, AsyncIterator, Callable, Optional, Awaitable, Union, List, Dict
from urllib.parse import quote

from loguru import logger
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
)

from github.clients.rest_client import RestClient
from github.helpers.utils import parse_file_content

PARSEABLE_EXTENSIONS = (".json", ".yaml", ".yml")


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

    async def get_organization(self, org_name: str) -> dict[str, Any]:
        """
        Get an organization by name.

        Args:
            org_name: Organization name

        Returns:
            Organization data
        """
        return await self.rest.send_api_request("GET", f"orgs/{org_name}")

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

    async def get_workflow_run(
        self, repo_path: str, run_id: int
    ) -> dict[str, Any]:
        """
        Get a workflow run by ID.

        Args:
            repo_path: Repository full name (owner/repo)
            run_id: Workflow run ID

        Returns:
            Workflow run data
        """
        return await self.rest.send_api_request(
            "GET", f"repos/{repo_path}/actions/runs/{run_id}"
        )

    async def get_workflow_job(
        self, repo_path: str, job_id: int
    ) -> dict[str, Any]:
        """
        Get a workflow job by ID.

        Args:
            repo_path: Repository full name (owner/repo)
            job_id: Job ID

        Returns:
            Workflow job data
        """
        return await self.rest.send_api_request(
            "GET", f"repos/{repo_path}/actions/jobs/{job_id}"
        )

    async def get_team_member(
        self, org_name: str, team_slug: str, username: str
    ) -> dict[str, Any]:
        """
        Get a team member.

        Args:
            org_name: Organization name
            team_slug: Team slug
            username: Username

        Returns:
            Team member data
        """
        return await self.rest.send_api_request(
            "GET", f"orgs/{org_name}/teams/{team_slug}/members/{username}"
        )

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

    async def get_repository_workflow_runs(
        self, repos_batch: list[dict[str, Any]], max_concurrent: int = 10
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        Get workflow runs for repositories.

        Args:
            repos_batch: Batch of repositories
            max_concurrent: Maximum concurrent requests

        Yields:
            Batches of workflow runs
        """
        return await self.get_repository_resource(
            repos_batch, "actions/runs", max_concurrent
        )

    async def get_repository_workflow_jobs(
        self, repos_batch: list[dict[str, Any]], max_concurrent: int = 10
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        Get workflow jobs for repositories.

        Args:
            repos_batch: Batch of repositories
            max_concurrent: Maximum concurrent requests

        Yields:
            Batches of workflow jobs
        """
        params = {"per_page": 100}

        async def _get_jobs(
            repo: dict[str, Any]
        ) -> AsyncIterator[list[dict[str, Any]]]:
            async for batch in self.rest.get_paginated_repo_resource(
                repo["full_name"], "actions/jobs", params=params
            ):
                yield batch
                break  # only yield first page

        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = [
            semaphore_async_iterator(
                semaphore,
                partial(_get_jobs, repo),
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

    async def file_exists(
        self, repo_path: str, path: str, ref: str = "main"
    ) -> bool:
        """
        Check if a file exists in a repository.

        Args:
            repo_path: Repository full name (owner/repo)
            path: Path to file in the repository
            ref: Git reference (branch, tag, commit)

        Returns:
            True if file exists, False otherwise
        """
        # GitHub doesn't have a direct "file exists" API, we need to try getting content
        try:
            result = await self.rest.send_api_request(
                "GET",
                f"repos/{quote(repo_path, safe='')}/contents/{quote(path, safe='')}",
                params={"ref": ref}
            )
            return bool(result)
        except Exception:
            return False


    async def _process_file(
        self, file: dict[str, Any], context: str, skip_parsing: bool = False
        ) -> dict[str, Any]:
        """
        Process a file entity, retrieving its content and optionally parsing it.

        Args:
            file: File metadata
            context: Context for logging
            skip_parsing: Whether to skip content parsing

        Returns:
            File data with content
        """
        repo_path = file.get("repo_path", "")
        file_path = file.get("path", "")
        ref = file.get("ref", "main")

        logger.debug(f"Processing file {file_path} from {repo_path} at {ref}")

        try:
            # Get file data from GitHub
            file_data = await self.rest.get_file_data(repo_path, file_path, ref)

            # Add context info
            file_data["repo_path"] = repo_path

            # Parse content if needed
            if (
                not skip_parsing
                and "content" in file_data
                and file_path.endswith(PARSEABLE_EXTENSIONS)
            ):
                try:
                    parsed_content = parse_file_content(
                        file_data["content"], file_path, context
                    )

                    # Resolve any file:// references in the content
                    parsed_content = await self._resolve_file_references(
                        parsed_content, repo_path, ref
                    )

                    file_data["content"] = parsed_content
                except Exception as e:
                    logger.error(f"Error parsing file {file_path}: {e}")

            return file_data

        except Exception as e:
            logger.error(f"Error processing file {file_path} from {repo_path}: {e}")
            return {
                "path": file_path,
                "repo_path": repo_path,
                "ref": ref,
                "error": str(e)
            }

    async def _resolve_file_references(
        self, data: Union[dict[str, Any], list[Any], Any], repo_path: str, ref: str
    ) -> Union[dict[str, Any], list[Any], Any]:
        """
        Find and replace file:// references with their content.

        Args:
            data: Data to process
            repo_path: Repository full name
            ref: Git reference

        Returns:
            Data with file references resolved
        """
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and value.startswith("file://"):
                    file_path = value[7:]
                    logger.debug(f"Resolving file reference to {file_path} in {repo_path}")
                    content = await self.get_file_content(repo_path, file_path, ref)
                    data[key] = content
                elif isinstance(value, (dict, list)):
                    data[key] = await self._resolve_file_references(
                        value, repo_path, ref
                    )

        elif isinstance(data, list):
            for index, item in enumerate(data):
                data[index] = await self._resolve_file_references(item, repo_path, ref)

        return data

    async def search_files(
        self,
        query: str,
        path: str,
        repositories: Optional[list[str]] = None,
        skip_parsing: bool = False,
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        Search for files in repositories.

        Args:
            query: Search query
            path: File path pattern
            repositories: List of repository full names
            skip_parsing: Whether to skip content parsing

        Yields:
            Batches of file data
        """
        search_query = f"{query} path:{path}"
        logger.info(f"Starting file search with query: '{search_query}'")

        if repositories:
            for repo in repositories:
                logger.info(f"Limiting search to repository: {repo}")
                search_query = f"{search_query} repo:{repo}"

        params = {
            "q": search_query,
            "per_page": 100,
        }

        async for batch in self.rest.get_paginated_resource("search/code", params=params):
            logger.debug(f"Found {len(batch)} files matching the search criteria")

            processed_batch = []
            for item in batch:
                if "repository" in item and "path" in item:
                    repo_path = item["repository"]["full_name"]
                    file_path = item["path"]

                    file_data = await self._process_file(
                        {"repo_path": repo_path, "path": file_path},
                        repo_path,
                        skip_parsing
                    )

                    if file_data:
                        processed_batch.append(file_data)

            if processed_batch:
                yield processed_batch

    async def get_team_members(
        self, org_name: str, team_slug: str
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """
        Get members of a team in an organization.

        Args:
            org_name: Organization name
            team_slug: Team slug
            include_bot_members: Whether to include bot users

        Yields:
            Batches of team members
        """
        async for batch in self.rest.get_paginated_resource(
            f"orgs/{org_name}/teams/{team_slug}/members"
        ):
            if batch:

                logger.info(
                    f"Received batch of {len(batch)} members for team {team_slug}"
                )
                yield batch

    async def _enrich_repo_with_languages(self, repo: dict[str, Any]) -> dict[str, Any]:
        """
        Enrich a repository with language information.

        Args:
            repo: Repository data

        Returns:
            Repository data with language information
        """
        repo_path = repo.get("full_name")
        logger.debug(f"Enriching {repo_path} with languages")
        languages = await self.rest.get_repo_languages(repo_path)
        logger.info(f"Fetched languages for {repo_path}: {languages}")
        repo["__languages"] = languages
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
            enrich_func: Function to enrich each item
            max_concurrent: Maximum concurrent operations

        Returns:
            Enriched batch
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        tasks = [self._enrich_item(item, enrich_func, semaphore) for item in batch]
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
            enrich_func: Function to enrich the item
            semaphore: Semaphore for concurrency control

        Returns:
            Enriched item
        """
        async with semaphore:
            return await enrich_func(item)

    async def enrich_organization_with_members(
        self, org: dict[str, Any], team_slug: str
    ) -> dict[str, Any]:
        """
        Enrich an organization with team members.

        Args:
            org: Organization data
            team_slug: Team slug
            include_bot_members: Whether to include bot users

        Returns:
            Organization with team members
        """
        logger.info(f"Enriching organization {org['login']} with team members")
        members = []

        async for members_batch in self.get_team_members(
            org['login'], team_slug
        ):
            for member in members_batch:
                members.append({
                    "login": member["login"],
                    "id": member["id"],
                    "name": member.get("name", ""),
                    "email": member.get("email", ""),
                })

        org["__members"] = members
        return org
