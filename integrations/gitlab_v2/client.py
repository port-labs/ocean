import asyncio
import httpx
from httpx import Timeout
from loguru import logger
from typing import Any, AsyncGenerator
from port_ocean.utils import http_async_client
from port_ocean.context.ocean import ocean
from port_ocean.utils.cache import cache_iterator_result

REQUEST_TIMEOUT: int = 60
CREATE_UPDATE_WEBHOOK_EVENTS: list[str] = [
    "open",
    "reopen",
    "update",
    "approved",
    "unapproved",
    "approval",
    "unapproval",
]
DELETE_WEBHOOK_EVENTS: list[str] = ["close", "merge"]
WEBHOOK_EVENTS_TO_TRACK: dict[str, bool] = {
    "issues_events": True,
    "merge_requests_events": True,
}
WEBHOOK_NAME: str = "Port-Ocean-Events-Webhook"


class GitlabClient:
    def __init__(self, gitlab_host: str, gitlab_token: str) -> None:
        self.projects_url = f"{gitlab_host}/api/v4/projects"
        self.merge_requests_url = f"{gitlab_host}/api/v4/merge_requests"
        self.issues_url = f"{gitlab_host}/api/v4/issues"
        self.groups_url = f"{gitlab_host}/api/v4/groups"

        self.gitlab_token = gitlab_token
        self.client = http_async_client
        self.client.headers.update({"Authorization": f"Bearer {gitlab_token}"})
        self.client.timeout = Timeout(REQUEST_TIMEOUT)

    async def _make_request(
            self,
            url: str,
            method: str = "GET",
            query_params: dict[str, Any] | None = None,
            json_data: dict[str, Any] | None = None,
            headers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        logger.info(f"Sending request to GitLab API: {method} {url}")
        try:
            response = await self.client.request(
                method=method,
                url=url,
                params=query_params,
                json=json_data,
                headers=headers,
            )
            response.raise_for_status()

            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Encountered an HTTP error with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        except httpx.HTTPError as e:
            logger.error(
                f"Encountered an HTTP error {e} while sending a request to {method} {url} with query_params: {query_params}"
            )
            raise

    @staticmethod
    def _default_paginated_req_params(
            page: int = 1, per_page: int = 50, owned: bool = True
    ) -> dict[str, Any]:
        return {
            "page": page,
            "per_page": per_page,
            "owned": owned,
        }

    async def _make_paginated_request(
            self, url: str, params: dict[str, Any] = {}
    ) -> AsyncGenerator[dict[str, Any], None]:
        params = {**self._default_paginated_req_params(), **params}
        next_page = True

        while next_page:
            logger.info(f"Making paginated request to {url} with params: {params}")
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                response_data = response.json()

                yield response_data

                # Check if there's a next page
                next_page = response.headers.get("X-Next-Page")
                if not next_page:
                    logger.info("No more pages to fetch, stopping pagination.")
                    break  # No more pages, exit the loop

                params["page"] = int(next_page)
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error with status code: {e.response.status_code}"
                    f" and response text: {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(f"HTTP occurred while fetching data {e}")
                raise

        logger.info("Finished paginated request")

    async def create_webhooks(self, app_host: str) -> None:
        await self._create_project_hook(app_host)

    @cache_iterator_result()
    async def get_projects(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for projects in self._make_paginated_request(self.projects_url):
            # fetch all project languages concurrently
            projects = await asyncio.gather(
                *[self._enrich_project_with_language(project) for project in projects]
            )

            # fetch all project groups concurrently
            projects = await asyncio.gather(
                *[self._enrich_project_with_group(project) for project in projects]
            )

            yield projects

    async def get_project(self, project_id: int) -> dict[str, Any]:
        return await self._make_request(f"{self.projects_url}/{project_id}")

    @cache_iterator_result()
    async def get_groups(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for groups in self._make_paginated_request(self.groups_url):
            yield groups

    async def get_merge_requests(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for merge_requests in self._make_paginated_request(
                self.merge_requests_url
        ):
            merge_requests = await asyncio.gather(
                *[
                    self._enrich_merge_request_with_project(merge_request)
                    for merge_request in merge_requests
                ]
            )

            yield merge_requests

    async def get_merge_request(
            self, project_id: int, merge_request_id: int
    ) -> dict[str, Any]:
        merge_request = await self._make_request(
            url=f"{self.projects_url}/{project_id}/merge_requests/{merge_request_id}"
        )

        return merge_request

    async def get_issues(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for issues in self._make_paginated_request(self.issues_url):
            issues = await asyncio.gather(
                *[self._enrich_issues_with_project(issue) for issue in issues]
            )

            yield issues

    async def _create_project_hook(self, app_host: str) -> None:
        gitlab_project_webhook_host = f"{app_host}/integration/webhook"
        async for projects in self.get_projects():
            # Create webhooks concurrently for each project
            await asyncio.gather(
                *[
                    self._process_project_hooks(project, gitlab_project_webhook_host)
                    for project in projects
                ]
            )

    async def _process_project_hooks(
            self, project: dict[str, Any], webhook_host: str
    ) -> None:
        try:
            hooks = await self._get_project_hooks(project["id"])

            # Create or skip the project hook
            await self._create_or_skip_project_hook(project, hooks, webhook_host)

        except Exception as e:
            logger.error(
                f"Error processing hooks for project {project['path_with_namespace']}: {e}"
            )

    async def _create_or_skip_project_hook(
            self, project: dict[str, Any], hooks: list[dict[str, Any]], webhook_host: str
    ) -> None:
        if any(
                hook["url"] == webhook_host for hook in hooks
        ):
            logger.info(
                f"Skipping hook creation for project {project['path_with_namespace']}"
            )
            return

        payload: dict[str, Any] = {
            "id": project["id"],
            "name": f"{ocean.config.integration.identifier}-{WEBHOOK_NAME}",
            "url": webhook_host,
            **WEBHOOK_EVENTS_TO_TRACK,
        }

        try:
            logger.info(f"Creating hook for project {project['path_with_namespace']}")
            await self._make_request(
                url=f"{self.projects_url}/{project['id']}/hooks",
                method="POST",
                json_data=payload,
            )
            logger.info(f"Created hook for project {project['path_with_namespace']}")
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Failed to create webhook for project {project['path_with_namespace']}: {e}"
            )

    async def _get_project_hooks(self, project_id: int) -> dict[str, Any]:
        url = f"{self.projects_url}/{project_id}/hooks"

        return await self._make_request(url)

    async def _get_project_languages(self, project_id: int) -> str:
        url = f"{self.projects_url}/{project_id}/languages"
        languages = await self._make_request(url)
        return ", ".join(languages.keys())

    async def _get_project_group(self, project_id: int) -> dict[str, Any]:
        url = f"{self.projects_url}/{project_id}/groups"

        return await self._make_request(url)

    async def _get_issue_project(self, project_id: int) -> dict[str, Any]:
        return await self.get_project(project_id)

    async def _get_merge_request_project(self, project_id: int) -> dict[str, Any]:
        return await self.get_project(project_id)

    async def _enrich_project_with_language(self, project: dict[str, Any]) -> dict[str, Any]:
        languages = await self._get_project_languages(project["id"])
        project["__languages"] = languages
        return project

    async def _enrich_project_with_group(self, project: dict[str, Any]) -> dict[str, Any]:
        group = await self._get_project_group(project["id"])
        project["__group"] = group
        return project

    async def _enrich_issues_with_project(self, issue: dict[str, Any]) -> dict[str, Any]:
        project = await self._get_issue_project(issue["project_id"])
        issue["__project"] = project
        return issue

    async def _enrich_merge_request_with_project(self, merge_request: dict[str, Any]) -> dict[str, Any]:
        project = await self._get_merge_request_project(merge_request["project_id"])
        merge_request["__project"] = project
        return merge_request

    async def _enrich_project_with_hooks(self, project: dict[str, Any]) -> dict[str, Any]:
        hooks = await self._get_project_hooks(project["id"])
        project["__hooks"] = hooks
        return project
