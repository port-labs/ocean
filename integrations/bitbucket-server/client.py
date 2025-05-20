import asyncio
import hashlib
import hmac
import re
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from aiolimiter import AsyncLimiter  # type: ignore
from fastapi import Request
from httpx import BasicAuth
from loguru import logger
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.utils.cache import cache_iterator_result

# Rate limit docs: https://support.atlassian.com/bitbucket-cloud/docs/api-request-limits/
BITBUCKET_RATE_LIMIT = 1000  # requests per hour
BITBUCKET_RATE_LIMIT_WINDOW = 3600  # 1 hour
README_PATTERN = re.compile(r"^readme(\.[a-z0-9]+)?$", re.IGNORECASE)

PROJECT_WEBHOOK_EVENTS = [
    "project:modified",
]

REPO_WEBHOOK_EVENTS = [
    "repo:modified",
    "repo:refs_changed",
]

PR_WEBHOOK_EVENTS = [
    "pr:modified",
    "pr:opened",
    "pr:merged",
    "pr:reviewer:updated",
    "pr:declined",
    "pr:deleted",
    "pr:comment:deleted",
    "pr:from_ref_updated",
    "pr:comment:edited",
    "pr:reviewer:unapproved",
    "pr:reviewer:needs_work",
    "pr:reviewer:approved",
    "pr:comment:added",
]


WEBHOOK_EVENTS = [
    *PROJECT_WEBHOOK_EVENTS,
    *REPO_WEBHOOK_EVENTS,
    *PR_WEBHOOK_EVENTS,
]


class BitbucketClient:
    """
    A client for interacting with the Bitbucket Server API.
    Handles authentication, rate limiting, and provides methods for accessing various Bitbucket resources.
    """

    def __init__(
        self,
        username: str,
        password: str,
        base_url: str,
        webhook_secret: str | None = None,
        app_host: str | None = None,
    ):
        """
        Initialize the Bitbucket client with authentication and configuration.

        Args:
            username: Bitbucket username for authentication
            password: Bitbucket password/token for authentication
            base_url: Base URL of the Bitbucket server
            webhook_secret: Optional secret for webhook signature verification
            app_host: Optional host URL for webhook callbacks
        """
        self.username = username
        self.password = password
        self.base_url = base_url
        self.bitbucket_auth = BasicAuth(username=username, password=password)
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60), auth=self.bitbucket_auth
        )
        self.app_host = app_host
        self.webhook_secret = webhook_secret
        # Despite this, being the rate limits, we do not reduce to the lowest common factor because we want to allow as much
        # concurrency as possible. This is because we expect most users to have resources
        # synced under one hour.
        self.rate_limiter = AsyncLimiter(
            BITBUCKET_RATE_LIMIT, BITBUCKET_RATE_LIMIT_WINDOW
        )

    async def send_port_request(
        self, method: str, path: str, payload: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Send an HTTP request to the Bitbucket API with rate limiting.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            payload: Optional request payload

        Returns:
            JSON response from the API
        """
        url = f"{self.base_url}/rest/api/1.0/{path}"
        async with self.rate_limiter:
            try:
                logger.info(
                    f"Sending {method} request to {url} with payload: {payload}"
                )
                response = await self.client.request(method, url, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(f"Failed to send {method} request to url {url}: {str(e)}")
                raise

    async def get_paginated_resource(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        page_size: int = 25,
        full_response: bool = False,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch paginated resources from the Bitbucket API.

        Args:
            path: API endpoint path
            params: Optional query parameters
            page_size: Number of items per page
            full_response: Whether to return full response or just values

        Yields:
            Batches of resource items
        """
        params = params or {}
        params["limit"] = page_size
        start = 0

        while True:
            params["start"] = start
            try:
                data = await self.send_port_request("GET", path, payload=params)
                values: list[dict[str, Any]] = data.get("values", [])
                if not values:
                    break

                if full_response:
                    yield [data]
                else:
                    yield values

                if data.get("isLastPage", True):
                    break

                start += page_size
            except httpx.HTTPError as e:
                logger.error(f"Error fetching paginated resource: {e}")
                break

    async def _get_all_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Internal method to fetch all projects from Bitbucket.

        Yields:
            Batches of project data
        """
        async for project_batch in self.get_paginated_resource("projects"):
            yield project_batch

    async def _get_projects_with_filter(
        self, projects_filter: set[str]
    ) -> list[dict[str, Any]]:
        """
        Internal method to fetch specific projects by their keys.

        Args:
            projects_filter: Set of project keys to fetch

        Returns:
            List of filtered project data
        """
        projects = dict[str, dict[str, Any]]()
        async for project_batch in self.get_projects():
            logger.info(f"Received project batch: {project_batch}")
            filtered_projects = filter(
                lambda project: project["key"] in projects_filter, project_batch
            )
            projects.update({project["key"]: project for project in filtered_projects})
            if len(projects) == len(projects_filter):
                break
        return list(projects.values())

    @cache_iterator_result()
    async def get_projects(
        self, projects_filter: Optional[set[str]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get projects from Bitbucket, optionally filtered by project keys.

        Args:
            projects_filter: Optional set of project keys to filter by

        Yields:
            Batches of project data
        """
        logger.info(f"Getting projects with filter: {projects_filter}")
        if projects_filter:
            project_batch = await self._get_projects_with_filter(projects_filter)
            yield project_batch
        else:
            async for project_batch in self._get_all_projects():
                yield project_batch

    async def _enrich_repository_with_readme_and_latest_commit(
        self, repository: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Internal method to enrich repository data with README and latest commit information.

        Args:
            repository: Repository data to enrich

        Returns:
            Enriched repository data
        """
        repository["__readme"] = await self.get_repository_readme(
            repository["project"]["key"], repository["slug"]
        )
        repository["__latestCommit"] = await self.get_latest_commit(
            repository["project"]["key"], repository["slug"]
        )
        return repository

    async def get_repositories_for_project(
        self, project_key: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get all repositories for a specific project.

        Args:
            project_key: Key of the project

        Yields:
            Batches of repository data
        """
        async for repo_batch in self.get_paginated_resource(
            f"projects/{project_key}/repos"
        ):
            repositories = []
            for repository in repo_batch:
                repositories.append(
                    await self._enrich_repository_with_readme_and_latest_commit(
                        repository
                    )
                )
            yield repositories

    @cache_iterator_result()
    async def get_repositories(
        self, projects_filter: set[str] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get repositories across multiple projects, optionally filtered by project keys.

        Args:
            projects_filter: Optional set of project keys to filter by

        Yields:
            Batches of repository data
        """
        tasks = []
        async for project_batch in self.get_projects(projects_filter):
            for project in project_batch:
                tasks.append(self.get_repositories_for_project(project["key"]))

        async for repo_batch in stream_async_iterators_tasks(*tasks):
            yield repo_batch

    async def _get_pull_requests_for_repository(
        self, project_key: str, repo_slug: str, state: str = "OPEN"
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Internal method to get pull requests for a specific repository.

        Args:
            project_key: Key of the project
            repo_slug: Slug of the repository
            state: State of pull requests to fetch (default: "OPEN")

        Yields:
            Batches of pull request data
        """
        params = {"state": state}
        async for pr_batch in self.get_paginated_resource(
            f"projects/{project_key}/repos/{repo_slug}/pull-requests",
            params=params,
        ):
            yield pr_batch

    @cache_iterator_result()
    async def get_pull_requests(
        self, projects_filter: set[str] | None = None, state: str = "OPEN"
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get pull requests across multiple repositories, optionally filtered by project keys.

        Args:
            projects_filter: Optional set of project keys to filter by
            state: State of pull requests to fetch (default: "OPEN")

        Yields:
            Batches of pull request data
        """
        tasks = []
        async for repo_batch in self.get_repositories(projects_filter):
            for repo in repo_batch:
                tasks.append(
                    self._get_pull_requests_for_repository(
                        repo["project"]["key"], repo["slug"], state
                    )
                )

        async for pr_batch in stream_async_iterators_tasks(*tasks):
            yield pr_batch

    async def get_users(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Get all users from Bitbucket.

        Yields:
            Batches of user data
        """
        async for user_batch in self.get_paginated_resource("users"):
            yield user_batch

    async def get_repository_readme(self, project_key: str, repo_slug: str) -> str:
        """
        Get the README content for a specific repository, regardless of casing or extension.
        """

        async def find_readme_file() -> str | None:
            file_listing_path = f"projects/{project_key}/repos/{repo_slug}/files"
            async for batch in self.get_paginated_resource(
                file_listing_path, page_size=500
            ):
                for file_path in batch:
                    if "/" not in file_path and README_PATTERN.match(file_path):
                        return file_path

            return None

        def parse_repository_file_response(file_response: Dict[str, Any]) -> str:
            lines = file_response.get("lines", [])
            return "\n".join(line.get("text", "") for line in lines)

        readme_filename = await find_readme_file()
        if not readme_filename:
            return ""
        file_path = f"projects/{project_key}/repos/{repo_slug}/browse/{readme_filename}"
        readme_content = ""

        async for readme_file_batch in self.get_paginated_resource(
            path=file_path, page_size=500, full_response=True
        ):
            readme_content += parse_repository_file_response(readme_file_batch)

        return readme_content

    async def get_latest_commit(
        self, project_key: str, repo_slug: str
    ) -> Dict[str, Any]:
        """
        Get the latest commit for a specific repository.

        Args:
            project_key: Key of the project
            repo_slug: Slug of the repository

        Returns:
            Latest commit data
        """
        response = await self.send_port_request(
            "GET",
            f"projects/{project_key}/repos/{repo_slug}/commits",
            payload={"limit": 1},
        )
        values = response.get("values")
        if not values:
            return {}
        return values[0]

    async def get_single_project(self, project_key: str) -> dict[str, Any]:
        """
        Get a single project by its key.

        Args:
            project_key: Key of the project

        Returns:
            Project data
        """
        project = await self.send_port_request("GET", f"projects/{project_key}")
        return project

    async def get_single_repository(
        self, project_key: str, repo_slug: str
    ) -> dict[str, Any]:
        """
        Get a single repository by project key and repository slug.

        Args:
            project_key: Key of the project
            repo_slug: Slug of the repository

        Returns:
            Repository data
        """
        repository = await self.send_port_request(
            "GET", f"projects/{project_key}/repos/{repo_slug}"
        )

        return await self._enrich_repository_with_readme_and_latest_commit(repository)

    async def get_single_pull_request(
        self, project_key: str, repo_slug: str, pr_key: str
    ) -> dict[str, Any]:
        """
        Get a single pull request by project key, repository slug, and PR key.

        Args:
            project_key: Key of the project
            repo_slug: Slug of the repository
            pr_key: Key of the pull request

        Returns:
            Pull request data
        """
        pull_request = await self.send_port_request(
            "GET",
            f"projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_key}",
        )
        return pull_request

    async def get_single_user(self, user_key: str) -> dict[str, Any]:
        """
        Get a single user by their key.

        Args:
            user_key: Key of the user

        Returns:
            User data
        """
        user = await self.send_port_request("GET", f"users/{user_key}")
        return user

    def _get_webhook_name(self, key: str) -> str:
        """
        Internal method to generate a webhook name.

        Args:
            key: Key to use in webhook name

        Returns:
            Generated webhook name
        """
        return f"Port Ocean - {key}"

    def _create_webhook_payload(
        self, key: str, events: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Internal method to create webhook payload.

        Args:
            key: Key to use in webhook configuration

        Returns:
            Webhook configuration payload
        """
        if not events:
            events = WEBHOOK_EVENTS
        name = self._get_webhook_name(key)
        payload = {
            "name": name,
            "url": f"{self.app_host}/integration/webhook",
            "events": events,
            "active": True,
            "sslVerificationRequired": True,
        }
        if self.webhook_secret:
            payload["configuration"] = {
                "secret": self.webhook_secret,
                "createdBy": "Port Ocean",
            }
        return payload

    async def get_project_webhooks(self, project_key: str) -> list[dict[str, Any]]:
        """
        Get webhooks for a specific project.

        Args:
            project_key: Key of the project

        Returns:
            List of webhook configurations
        """
        webhooks = await self.send_port_request(
            "GET", f"projects/{project_key}/webhooks"
        )
        return webhooks.get("values", [])

    async def _create_project_webhook(self, project_key: str) -> dict[str, Any]:
        """
        Internal method to create a webhook for a project.

        Args:
            project_key: Key of the project

        Returns:
            Created webhook configuration
        """
        existing_webhooks = await self.get_project_webhooks(project_key)
        existing_webhook_names = set(webhook["name"] for webhook in existing_webhooks)
        if self._get_webhook_name(project_key) in existing_webhook_names:
            logger.info(
                f"Webhook for project {project_key} already exists, skipping creation"
            )
            return

        webhook_payload = self._create_webhook_payload(project_key)
        webhook = await self.send_port_request(
            "POST",
            f"projects/{project_key}/webhooks",
            payload=webhook_payload,
        )
        return webhook

    async def _create_projects_webhook(self, projects: set[str]) -> None:
        """
        Internal method to create webhooks for multiple projects.

        Args:
            projects: Set of project keys
        """
        logger.info(f"Creating webhooks for projects: {projects}")
        project_tasks = []
        for project_key in projects:
            project_tasks.append(self._create_project_webhook(project_key))

        await asyncio.gather(*project_tasks)

    async def create_projects_webhook(self, projects: set[str] | None = None) -> None:
        """
        Create webhooks for projects, optionally filtered by project keys.

        Args:
            projects: Optional set of project keys to create webhooks for
        """
        if projects:
            await self._create_projects_webhook(projects)
        else:
            async for project_batch in self.get_projects():

                await self._create_projects_webhook(
                    set(project["key"] for project in project_batch)
                )

    async def get_repository_webhooks(
        self, project_key: str, repo_slug: str
    ) -> list[dict[str, Any]]:
        """
        Get webhooks for a specific repository.

        Args:
            project_key: Key of the project
            repo_slug: Slug of the repository

        Returns:
            List of webhook configurations
        """
        webhooks = await self.send_port_request(
            "GET", f"projects/{project_key}/repos/{repo_slug}/webhooks"
        )
        return webhooks.get("values", [])

    async def _create_repository_webhook(
        self, project_key: str, repo_slug: str
    ) -> dict[str, Any]:
        """
        Internal method to create a webhook for a repository.

        Args:
            project_key: Key of the project
            repo_slug: Slug of the repository

        Returns:
            Created webhook configuration
        """
        existing_webhooks = await self.get_repository_webhooks(project_key, repo_slug)
        existing_webhook_names = set(webhook["name"] for webhook in existing_webhooks)
        if (
            self._get_webhook_name(f"{project_key}-{repo_slug}")
            in existing_webhook_names
        ):
            logger.info(
                f"Webhook for repository {repo_slug} already exists, skipping creation"
            )
            return

        webhook_payload = self._create_webhook_payload(
            f"{project_key}-{repo_slug}",
            events=[
                *PR_WEBHOOK_EVENTS,
                *REPO_WEBHOOK_EVENTS,
            ],
        )
        webhook = await self.send_port_request(
            "POST",
            f"projects/{project_key}/repos/{repo_slug}/webhooks",
            payload=webhook_payload,
        )
        return webhook

    async def _create_project_repositories_webhook(self, projects: set[str]) -> None:
        """
        Internal method to create webhooks for all repositories in a project.

        Args:
            projects: Set of project keys
        """
        tasks = []
        for project_key in projects:
            async for repo_batch in self.get_repositories(project_key):
                for repo in repo_batch:
                    tasks.append(
                        self._create_repository_webhook(
                            repo["project"]["key"], repo["slug"]
                        )
                    )

        await asyncio.gather(*tasks)

    async def create_repositories_webhooks(
        self, projects: set[str] | None = None
    ) -> None:
        """
        Create webhooks for repositories, optionally filtered by project keys.

        Args:
            projects: Optional set of project keys to create webhooks for
        """
        if projects:
            await self._create_project_repositories_webhook(projects)
        else:
            async for project_batch in self.get_projects():
                await self._create_project_repositories_webhook(
                    set(project["key"] for project in project_batch)
                )

    async def _get_application_properties(self) -> dict[str, Any]:
        """
        Internal method to get Bitbucket application properties.

        Returns:
            Application properties data
        """
        return await self.send_port_request(
            method="GET",
            path="application-properties",
        )

    async def is_version_8_point_7_and_older(self) -> bool:
        """
        Check if the Bitbucket server version is 8.7 or older.

        Returns:
            True if version is 8.7 or older, False otherwise
        """
        application_properties = await self._get_application_properties()
        # we intentionally do not use get to ensure the integration
        # fails early if there is a problem
        version: str = application_properties["version"]
        # keep only the first two numbers in the version leaving the rest
        # and converting the result to a float for easy comparison
        float_version = float(".".join(version.split(".")[:2]))
        return float_version <= 8.7

    async def setup_webhooks(self, projects: set[str] | None = None) -> None:
        """
        Set up webhooks for projects or repositories based on Bitbucket version.

        Args:
            projects: Optional set of project keys to set up webhooks for
        """
        if await self.is_version_8_point_7_and_older():
            await self.create_repositories_webhooks(projects)
        else:
            await self.create_projects_webhook(projects)

    async def verify_webhook_signature(self, request: Request) -> bool:
        """
        Verify webhook request signature.

        Args:
            request: Incoming webhook request

        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            logger.warning(
                "No secret provided for authenticating incoming webhooks, skipping authentication."
            )
            return True

        signature = request.headers.get("x-hub-signature")
        if not signature:
            logger.error("No signature found in request")
            return False

        body = await request.body()
        hash_object = hmac.new(self.webhook_secret.encode(), body, hashlib.sha256)
        expected_signature = "sha256=" + hash_object.hexdigest()

        if not signature.startswith("sha256="):
            signature = "sha256=" + signature

        return hmac.compare_digest(signature, expected_signature)

    async def healthcheck(self) -> None:
        """
        Perform a health check of the Bitbucket connection.

        Raises:
            Exception: If connection to Bitbucket fails
        """
        try:
            await self._get_application_properties()
            logger.info("Successfully connected to Bitbucket Server")
        except Exception as e:
            logger.error(f"Failed to connect to Bitbucket Server: {e}")
            raise ConnectionError("Failed to connect to Bitbucket Server") from e
