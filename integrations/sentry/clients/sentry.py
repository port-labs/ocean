from typing import Any, AsyncGenerator

from loguru import logger

from port_ocean.utils import http_async_client


class SentryClient:
    def __init__(
        self, sentry_base_url: str, auth_token: str, sentry_organization: str
    ) -> None:
        self.sentry_base_url = sentry_base_url
        self.auth_token = auth_token
        self.base_headers = {"Authorization": "Bearer " + f"{self.auth_token}"}
        self.api_url = f"{self.sentry_base_url}/api/0"
        self.organization = sentry_organization
        self.client = http_async_client
        self.client.headers.update(self.base_headers)

    async def get_paginated_projects(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        per_page = 100
        page = 0
        logger.info("Getting projects from Sentry")
        while True:
            project_response = await self.client.get(
                f"{self.api_url}/projects/?per_page={per_page}&cursor={page}:1:0"
            )
            project_response.raise_for_status()
            projects = project_response.json()
            logger.info(f"Got {len(projects)} projects from Sentry")
            yield projects
            page += 1
            if len(projects) < per_page:
                break

    async def get_issues(self, project_slug: str) -> list[dict[str, Any]]:
        logger.info(f"Getting issues from Sentry for project {project_slug}")
        issue_response = await self.client.get(
            f"{self.api_url}/projects/{self.organization}/{project_slug}/issues/"
        )
        issue_response.raise_for_status()
        issues = issue_response.json()
        logger.info(f"Got {len(issues)} issues from Sentry for project {project_slug}")
        return issues
