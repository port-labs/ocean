from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from aiolimiter import AsyncLimiter
from httpx import BasicAuth
from loguru import logger
from port_ocean.utils.cache import cache_iterator_result

BITBUCKET_RATE_LIMIT = 1000  # requests per hour
BITBUCKET_RATE_LIMIT_WINDOW = 3600  # 1 hour
WEBHOOK_EVENTS = [
    "repo:modified",
    "project:modified",
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


class BitbucketClient:
    def __init__(
        self,
        username: str,
        password: str,
        base_url: str,
        app_host: str = None,
    ):
        self.username = username
        self.password = password
        self.base_url = base_url
        self.bitbucket_auth = BasicAuth(username=username, password=password)
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60), auth=self.bitbucket_auth
        )
        self.app_host = app_host
        # Despite this, being the rate limits, we do not reduce to the lowest common factor because we want to allow as much
        # concurrency as possible. This is because we expect most users to have resources
        # synced under one hour.
        self.rate_limiter = AsyncLimiter(
            BITBUCKET_RATE_LIMIT, BITBUCKET_RATE_LIMIT_WINDOW
        )

    async def send_port_request(
        self, method: str, endpoint: str, payload: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        async with self.rate_limiter:
            try:
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
        params = params or {}
        params["limit"] = page_size
        start = 0

        while True:
            params["start"] = start
            try:
                data = await self.send_port_request(
                    "GET", f"rest/api/1.0/{path}", payload=params
                )
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
        async for project_batch in self.get_paginated_resource("projects"):
            yield project_batch

    async def _get_projects_with_filter(
        self, projects_filter: set[str]
    ) -> list[dict[str, Any]]:
        projects = dict[str, dict[str, Any]]()
        async for project_batch in self.get_projects():
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
        if projects_filter:
            project_batch = await self._get_projects_with_filter(projects_filter)
            yield project_batch
        else:
            async for project_batch in self._get_all_projects():
                yield project_batch

    async def _enrich_repository_with_readme_and_latest_commit(
        self, repository: dict[str, Any]
    ) -> dict[str, Any]:
        repository["__readme"] = await self.get_repository_readme(
            repository["project"]["key"], repository["slug"]
        )
        repository["__latestCommit"] = await self.get_latest_commit(
            repository["project"]["key"], repository["slug"]
        )
        return repository

    @cache_iterator_result()
    async def get_repositories(
        self, project_key: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
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
    async def get_pull_requests(
        self, project_key: str, repo_slug: str, state: str = "OPEN"
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = {"state": state}
        async for pr_batch in self.get_paginated_resource(
            f"projects/{project_key}/repos/{repo_slug}/pull-requests",
            params=params,
        ):
            yield pr_batch

    async def get_users(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for user_batch in self.get_paginated_resource("users"):
            yield user_batch

    async def get_repository_readme(self, project_key: str, repo_slug: str) -> str:
        def parse_repository_file_response(file_response: Dict[str, Any]) -> str:
            lines = file_response.get("lines", [])
            logger.info(f"Received readme file with {len(lines)} entries")
            readme_content = ""

            for line in lines:
                readme_content += line.get("text", "") + "\n"

            return readme_content

        file_path = f"projects/{project_key}/repos/{repo_slug}/browse/README.md"
        readme_content = ""
        async for readme_file_batch in self.get_paginated_resource(
            path=file_path, page_size=500, full_response=True
        ):
            file_content = parse_repository_file_response(readme_file_batch)
        readme_content += file_content
        return readme_content

    async def get_latest_commit(
        self, project_key: str, repo_slug: str
    ) -> Dict[str, Any]:
        response = await self.send_port_request(
            "GET",
            f"rest/api/1.0/projects/{project_key}/repos/{repo_slug}/commits",
            params={"limit": 1},
        )
        return response.get("values", [{}])[0]

    async def get_single_project(self, project_key: str) -> dict[str, Any]:
        project = await self.send_port_request(
            "GET", f"rest/api/1.0/projects/{project_key}"
        )
        return project

    async def get_single_repository(
        self, project_key: str, repo_slug: str
    ) -> dict[str, Any]:
        repository = await self.send_port_request(
            "GET", f"rest/api/1.0/projects/{project_key}/repos/{repo_slug}"
        )
        return repository

    async def get_single_pull_request(
        self, project_key: str, repo_slug: str, pr_key: str
    ) -> dict[str, Any]:
        pull_request = await self.send_port_request(
            "GET",
            f"rest/api/1.0/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_key}",
        )
        return pull_request

    async def get_single_user(self, user_key: str) -> dict[str, Any]:
        user = await self.send_port_request("GET", f"rest/api/1.0/users/{user_key}")
        return user

    def _create_webhook_payload(self, project_key: str) -> dict[str, Any]:
        name = f"Port Ocean - {project_key}"
        return {
            "name": name,
            "url": f"{self.app_host}/webhooks",
            "events": WEBHOOK_EVENTS,
        }

    async def get_project_webhooks(
        self, project_key: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for webhook_batch in self.get_paginated_resource(
            f"projects/{project_key}/webhooks"
        ):
            yield webhook_batch

    async def get_repository_webhooks(
        self, project_key: str, repo_slug: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for webhook_batch in self.get_paginated_resource(
            f"projects/{project_key}/repos/{repo_slug}/webhooks"
        ):
            yield webhook_batch

    async def create_project_webhook(self, project_key: str) -> dict[str, Any]:
        webhook = await self.send_port_request(
            "POST",
            f"rest/api/1.0/projects/{project_key}/webhooks",
            payload={"events": WEBHOOK_EVENTS},
        )
        return webhook
