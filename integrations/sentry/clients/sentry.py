from itertools import chain
from typing import Any, AsyncGenerator, AsyncIterator, cast, Optional, List

import httpx
from integration import SentryResourceConfig
from loguru import logger
from port_ocean.context.event import event
from port_ocean.utils import http_async_client
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.utils.cache import cache_iterator_result

from .exceptions import IgnoredError, ResourceNotFoundError
from .rate_limiter import SentryRateLimiter

PAGE_SIZE = 100


def flatten_list(lst: list[Any]) -> list[Any]:
    return list(chain.from_iterable(lst))


class SentryClient:
    _DEFAULT_IGNORED_ERRORS = [
        IgnoredError(
            status=401,
            message="Unauthorized access to endpoint — authentication required or token invalid",
            type="UNAUTHORIZED",
        ),
        IgnoredError(
            status=403,
            message="Forbidden access to endpoint — insufficient permissions",
            type="FORBIDDEN",
        ),
    ]

    def __init__(
        self, sentry_base_url: str, auth_token: str, sentry_organization: str
    ) -> None:
        self.sentry_base_url = sentry_base_url
        self.auth_token = auth_token
        self.base_headers = {"Authorization": "Bearer " + f"{self.auth_token}"}
        self.api_url = f"{self.sentry_base_url}/api/0"
        self.organization = sentry_organization
        self._client = http_async_client
        self.selector = cast(SentryResourceConfig, event.resource_config).selector
        self._rate_limiter = SentryRateLimiter()

    @staticmethod
    def get_next_link(link_header: str) -> str:
        """Information about the next page of results is provided in the link header. The pagination cursors are returned for both the previous and the next page.
        One of the URLs in the link response has rel=next, which indicates the next results page. It also has results=true, which means that there are more results.
        You can find more information about pagination in Sentry here: https://docs.sentry.io/api/pagination/
        """
        if link_header:
            links = link_header.split(",")
            for link in links:
                parts = link.strip().split(";")
                url = parts[0].strip("<>")
                rel = parts[1].strip()
                results = parts[2].strip()
                if 'rel="next"' in rel and 'results="true"' in results:
                    return url
        return ""

    def _should_ignore_error(
        self,
        error: httpx.HTTPStatusError,
        resource: str,
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> bool:
        all_ignored_errors = (ignored_errors or []) + self._DEFAULT_IGNORED_ERRORS
        status_code = error.response.status_code

        for ignored_error in all_ignored_errors:
            if str(status_code) == str(ignored_error.status):
                logger.warning(
                    f"Failed to fetch resources at {resource} due to {ignored_error.message}"
                )
                return True
        return False

    async def send_api_request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[dict[str, Any]] = None,
        ignored_errors: Optional[List[IgnoredError]] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Sends an API request with rate limiting and robust error handling.
        This method centralizes all Sentry API calls.

        Args:
            method (str): The HTTP method (e.g., "GET", "POST").
            url (str): The URL endpoint (relative or absolute).
            params (dict[str, Any]): Optional query parameters.
            ignored_errors (List[IgnoredError]): Optional list of ignored errors.
            **kwargs: Additional keyword arguments for httpx.AsyncClient.request.

        Returns:
            httpx.Response: The response from the API.

        Raises:
            ResourceNotFoundError: If the response status code is 404.
            httpx.HTTPStatusError: For any other non-2xx status codes
                                   (except 401, 403, and 404).
        """
        async with self._rate_limiter:
            full_url = (
                url if url.startswith("http") else f"{self.api_url}/{url.lstrip('/')}"
            )
            try:
                response = await self._client.request(
                    method, full_url, params=params, headers=self.base_headers, **kwargs
                )
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if self._should_ignore_error(e, url, ignored_errors):
                    return httpx.Response(200, content=b"{}")
                # Handle 404 specifically for ResourceNotFoundError
                if e.response.status_code == 404:
                    raise ResourceNotFoundError(f"Resource not found at {full_url}")
                else:
                    raise
            except httpx.HTTPError:
                # Re-raise non-HTTP status errors
                raise

    async def _get_paginated_resource(
        self, url: str, ignored_errors: Optional[List[IgnoredError]] = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params: dict[str, Any] = {"per_page": PAGE_SIZE}
        logger.debug(f"Getting paginated resource from Sentry for URL: {url}")

        while url:
            try:
                response = await self.send_api_request(
                    "GET", url, params=params, ignored_errors=ignored_errors
                )
                params["cursor"] = response.headers.get(
                    "X-Sentry-Next-Cursor"
                ) or response.headers.get("X-Sentry-Cursor")
                records = response.json()
                logger.debug(
                    f"Received {len(records)} records from Sentry for URL: {url}"
                )
                yield records

                url = self.get_next_link(response.headers.get("link", ""))
            except httpx.HTTPStatusError:
                logger.debug(f"Ignoring non-fatal error for paginated resource: {url}")
                return

    async def _get_single_resource(self, url: str) -> list[dict[str, Any]]:
        logger.debug(f"Getting single resource from Sentry for URL: {url}")
        try:
            response = await self.send_api_request("GET", url)
            return response.json()
        except httpx.HTTPStatusError:
            logger.debug(f"Ignoring non-fatal error for single resource: {url}")
            return []

    async def _get_project_tags_iterator(
        self, project: dict[str, Any]
    ) -> AsyncIterator[list[dict[str, Any]]]:
        try:
            url = f"{self.api_url}/projects/{self.organization}/{project['slug']}/tags/{self.selector.tag}/values/"
            tags = await self._get_single_resource(url)
            yield [{**project, "__tags": tag} for tag in tags]
        except ResourceNotFoundError:
            logger.debug(
                f"No values found for project {project['slug']} and tag {self.selector.tag} in {self.organization}"
            )
            yield []

    async def _get_issue_tags_iterator(
        self, issue: dict[str, Any]
    ) -> AsyncIterator[list[dict[str, Any]]]:
        try:
            url = f"{self.api_url}/organizations/{self.organization}/issues/{issue['id']}/tags/{self.selector.tag}/values/"
            tags = await self._get_single_resource(url)
            yield [{**issue, "__tags": tags}]
        except ResourceNotFoundError:
            logger.debug(
                f"No values found for issue {issue['id']} and tag {self.selector.tag} in {self.organization}"
            )
            yield []

    @cache_iterator_result()
    async def get_paginated_projects(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for project in self._get_paginated_resource(f"{self.api_url}/projects/"):
            yield project

    @cache_iterator_result()
    async def get_paginated_project_slugs(self) -> AsyncGenerator[list[str], None]:
        async for projects in self.get_paginated_projects():
            project_slugs = [project["slug"] for project in projects]
            yield project_slugs

    async def get_paginated_issues(
        self, project_slug: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for issues in self._get_paginated_resource(
            f"{self.api_url}/projects/{self.organization}/{project_slug}/issues/",
        ):
            yield issues

    async def get_issues_tags_from_issues(
        self, issues: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        add_tags_to_issues_tasks = [
            self._get_issue_tags_iterator(issue) for issue in issues
        ]
        issues_with_tags = []
        async for issues_with_tags_batch in stream_async_iterators_tasks(
            *add_tags_to_issues_tasks
        ):
            issues_with_tags.append(issues_with_tags_batch)
        return flatten_list(issues_with_tags)

    async def get_projects_tags_from_projects(
        self, projects: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        project_tags = []
        tasks = [self._get_project_tags_iterator(project) for project in projects]
        async for project_tags_batch in stream_async_iterators_tasks(*tasks):
            if project_tags_batch:
                project_tags.append(project_tags_batch)
        return flatten_list(project_tags)

    async def get_paginated_teams(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for teams in self._get_paginated_resource(
            f"{self.api_url}/organizations/{self.organization}/teams/"
        ):
            yield teams

    async def get_paginated_users(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for users in self._get_paginated_resource(
            f"{self.api_url}/organizations/{self.organization}/members/"
        ):
            yield users

    async def get_team_members(self, team_slug: str) -> list[dict[str, Any]]:
        logger.info(f"Getting team members for team {team_slug}")
        team_members_List = []
        async for team_members_batch in self._get_paginated_resource(
            f"{self.api_url}/teams/{self.organization}/{team_slug}/members/"
        ):
            logger.info(
                f"Received a batch of {len(team_members_batch)} members for team {team_slug}"
            )
            team_members_List.extend(team_members_batch)
        logger.info(
            f"Received a total of {len(team_members_List)} members for team {team_slug}"
        )
        return team_members_List
