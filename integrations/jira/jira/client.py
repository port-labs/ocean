import asyncio
import uuid
from typing import Any, AsyncGenerator, Generator, NamedTuple, Optional, cast

import httpx
from httpx import Auth, BasicAuth, Request, Response, Timeout
from loguru import logger

from port_ocean.clients.auth.oauth_client import OAuthClient
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client
from .rate_limiter import JiraRateLimiter

PAGE_SIZE = 50


class IgnoredError(NamedTuple):
    """Represents an error that should be ignored (logged but not raised)."""

    status: int | str
    message: Optional[str] = None
    type: Optional[str] = None


WEBHOOK_NAME = "Port-Ocean-Events-Webhook"
MAX_CONCURRENT_REQUESTS = 10

WEBHOOK_EVENTS = [
    "jira:issue_created",
    "jira:issue_updated",
    "jira:issue_deleted",
    "project_created",
    "project_updated",
    "project_deleted",
    "project_soft_deleted",
    "project_restored_deleted",
    "project_archived",
    "project_restored_archived",
    "user_created",
    "user_updated",
    "user_deleted",
]

OAUTH2_WEBHOOK_EVENTS = [
    "jira:issue_created",
    "jira:issue_updated",
    "jira:issue_deleted",
]


class BearerAuth(Auth):
    def __init__(self, token: str):
        self.token = token

    def auth_flow(self, request: Request) -> Generator[Request, Response, None]:
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request


class JiraClient(OAuthClient):
    jira_api_auth: Auth

    def __init__(self, jira_url: str, jira_email: str, jira_token: str) -> None:
        super().__init__()
        self.jira_url = jira_url
        self.jira_rest_url = f"{self.jira_url}/rest"
        self.jira_email = jira_email
        self.jira_token = jira_token

        # If the Jira URL is directing to api.atlassian.com, we use OAuth2 Bearer Auth
        if self.is_oauth_enabled():
            self.jira_api_auth = self._get_bearer()
            self.webhooks_url = f"{self.jira_rest_url}/api/3/webhook"
        else:
            self.jira_api_auth = BasicAuth(self.jira_email, self.jira_token)
            self.webhooks_url = f"{self.jira_rest_url}/webhooks/1.0/webhook"

        self.api_url = f"{self.jira_rest_url}/api/3"
        self.teams_base_url = f"{self.jira_url}/gateway/api/public/teams/v1/org"

        self.client = http_async_client
        self.client.auth = self.jira_api_auth
        self.client.timeout = Timeout(30)
        self._rate_limiter = JiraRateLimiter(max_concurrent=MAX_CONCURRENT_REQUESTS)

    _DEFAULT_IGNORED_ERRORS = [
        IgnoredError(
            status=403,
            message="Forbidden — insufficient permissions to access this resource",
            type="FORBIDDEN",
        ),
        IgnoredError(
            status=404,
            message="Resource not found or not accessible",
            type="NOT_FOUND",
        ),
    ]

    # 400 errors for JQL queries - only used for search endpoints where
    # permission issues can cause 400s (e.g., JQL referencing inaccessible projects)
    _JQL_IGNORED_ERRORS = [
        IgnoredError(
            status=400,
            message="Bad Request — may indicate permission issues or invalid JQL query",
            type="BAD_REQUEST",
        ),
    ]

    def _get_bearer(self) -> BearerAuth:
        try:
            return BearerAuth(self.external_access_token)
        except ValueError:
            return BearerAuth(self.jira_token)

    def refresh_request_auth_creds(self, request: httpx.Request) -> httpx.Request:
        return next(self._get_bearer().auth_flow(request))

    def _should_ignore_error(
        self,
        error: httpx.HTTPStatusError,
        url: str,
        method: str,
        ignored_errors: Optional[list[IgnoredError]] = None,
    ) -> bool:
        """Check if an HTTP error should be ignored (logged but not raised).

        Args:
            error: The HTTP status error to check
            url: The URL that was requested
            method: The HTTP method used
            ignored_errors: Additional errors to ignore for this request

        Returns:
            True if the error should be ignored, False otherwise
        """
        all_ignored_errors = (ignored_errors or []) + (
            self._DEFAULT_IGNORED_ERRORS if self._DEFAULT_IGNORED_ERRORS else []
        )
        status_code = error.response.status_code

        for ignored_error in all_ignored_errors:
            if str(status_code) == str(ignored_error.status):
                logger.warning(
                    f"Failed to {method} resources at {url} due to {ignored_error.message} "
                    f"with status code {status_code}"
                )
                return True
        return False

    async def _send_api_request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        ignored_errors: Optional[list[IgnoredError]] = None,
    ) -> dict[str, Any]:
        """Send a request to the Jira API with error handling and rate limiting.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: The URL to request
            params: Query parameters
            json: JSON body data
            headers: Additional headers
            ignored_errors: Additional errors to ignore for this request

        Returns:
            JSON response data, or empty dict {} if an ignored error occurred
        """
        try:
            async with self._rate_limiter:
                response = await self.client.request(
                    method=method, url=url, params=params, json=json, headers=headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            response = e.response
            if self._should_ignore_error(e, url, method, ignored_errors):
                return {}

            logger.error(
                f"Jira API request failed with status {e.response.status_code}: {method} {url}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to Jira API: {method} {url} - {str(e)}")
            raise
        finally:
            if "response" in locals():
                await self._rate_limiter.update_rate_limit_headers(response.headers)

    async def _get_paginated_data(
        self,
        url: str,
        extract_key: str | None = None,
        initial_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = initial_params or {}
        params |= self._generate_base_req_params()

        start_at = 0
        while True:
            params["startAt"] = start_at
            response_data = await self._send_api_request("GET", url, params=params)

            if not response_data:
                break

            items = cast(
                list[dict[str, Any]],
                response_data.get(extract_key, []) if extract_key else response_data,
            )

            if not items:
                break

            yield items

            start_at += len(items)

            if "total" in response_data and start_at >= response_data["total"]:
                break

    async def _get_cursor_paginated_data(
        self,
        url: str,
        method: str,
        extract_key: str,
        initial_params: dict[str, Any] | None = None,
        cursor_param: str = "cursor",
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = initial_params or {}
        cursor = params.get(cursor_param)

        while True:
            if cursor:
                params[cursor_param] = cursor

            response_data = await self._send_api_request(method, url, params=params)

            if not response_data:
                break

            items = response_data.get(extract_key, [])
            if not items:
                break

            yield items

            if page_info := response_data.get("pageInfo", {}):
                cursor = page_info.get("endCursor")
                if not page_info.get("hasNextPage", False):
                    break
            else:
                cursor = response_data.get("cursor")
                if not cursor:
                    break

    @staticmethod
    def _generate_base_req_params(
        maxResults: int = PAGE_SIZE, startAt: int = 0
    ) -> dict[str, Any]:
        return {
            "maxResults": maxResults,
            "startAt": startAt,
        }

    async def has_webhook_permission(self) -> bool:
        logger.info(f"Checking webhook permissions for Jira instance: {self.jira_url}")
        response = await self._send_api_request(
            method="GET",
            url=f"{self.api_url}/mypermissions",
            params={"permissions": "ADMINISTER"},
        )
        if not response:
            logger.warning("Failed to check webhook permissions - empty response")
            return False
        has_permission = response["permissions"]["ADMINISTER"]["havePermission"]

        return has_permission

    async def _create_events_webhook_oauth(self, app_host: str) -> None:
        webhook_target_app_host = f"{app_host}/integration/webhook"
        response = await self._send_api_request("GET", url=self.webhooks_url)
        if not response:
            logger.warning(
                "Failed to get webhooks - empty response, skipping webhook creation"
            )
            return
        webhooks = response.get("values", [])
        if len(webhooks) > 0:
            # jira allows for only one webhook per user per oauth app that is why we are always checking the first webhook
            existing_webhook_url = webhooks[0].get("url")
            if existing_webhook_url == webhook_target_app_host:
                logger.info("Ocean real time reporting webhook already exists")
            else:
                logger.warning(
                    f"Ocean real time reporting webhook already exists: {existing_webhook_url} attempted to create webhook: {webhook_target_app_host}"
                )
                logger.warning(
                    "If you'd like to use a different webhook, please contact support."
                )
            return

        # We search a random project to get data from all projects
        random_project = str(uuid.uuid4())

        body = {
            "url": webhook_target_app_host,
            "webhooks": [
                {
                    "jqlFilter": f"project not in ({random_project})",
                    "events": OAUTH2_WEBHOOK_EVENTS,
                }
            ],
        }

        await self._send_api_request("POST", self.webhooks_url, json=body)
        logger.info("Ocean real time reporting webhook created")

    async def create_webhooks(self, app_host: str) -> None:
        """Create webhooks if the user has permission."""
        if self.is_oauth_enabled():
            await self._create_events_webhook_oauth(app_host)
        else:
            if not await self.has_webhook_permission():
                logger.warning(
                    f"Cannot create webhooks for {self.jira_url}: Ensure the token has Jira Administrator rights."
                )
                return
            await self._create_events_webhook(app_host)

    async def _create_events_webhook(self, app_host: str) -> None:
        webhook_target_app_host = f"{app_host}/integration/webhook"
        webhooks = await self._send_api_request("GET", url=self.webhooks_url)

        if not webhooks:
            logger.warning(
                "Failed to get webhooks - empty response, attempting to create webhook"
            )
        elif isinstance(webhooks, list):
            for webhook in webhooks:
                if webhook.get("url") == webhook_target_app_host:
                    logger.info("Ocean real time reporting webhook already exists")
                    return

        body = {
            "name": f"{ocean.config.integration.identifier}-{WEBHOOK_NAME}",
            "url": webhook_target_app_host,
            "events": WEBHOOK_EVENTS,
        }

        await self._send_api_request("POST", self.webhooks_url, json=body)
        logger.info("Ocean real time reporting webhook created")

    async def get_single_project(self, project_key: str) -> dict[str, Any]:
        return await self._send_api_request(
            "GET", f"{self.api_url}/project/{project_key}"
        )

    async def get_paginated_projects(
        self, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting projects from Jira")
        async for projects in self._get_paginated_data(
            f"{self.api_url}/project/search", "values", initial_params=params
        ):
            yield projects

    async def get_single_issue(self, issue_key: str) -> dict[str, Any]:
        return await self._send_api_request("GET", f"{self.api_url}/issue/{issue_key}")

    async def _get_paginated_data_using_next_page_token(
        self,
        url: str,
        extract_key: str | None = None,
        initial_params: dict[str, Any] | None = None,
        ignored_errors: Optional[list[IgnoredError]] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get paginated data using token-based pagination for JQL endpoints."""
        params = initial_params or {}
        next_page_token = None

        while True:
            if next_page_token:
                params["nextPageToken"] = next_page_token

            response_data = await self._send_api_request(
                "GET", url, params=params, ignored_errors=ignored_errors
            )

            if not response_data:
                break

            items = cast(
                list[dict[str, Any]],
                response_data.get(extract_key, []) if extract_key else response_data,
            )

            if not items:
                break

            yield items

            next_page_token = response_data.get("nextPageToken")
            if not next_page_token:
                break

    async def get_paginated_issues(
        self, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting issues from Jira")
        params = params or {}
        logger.info(f"Using JQL filter: {params.get('jql', '')}")
        url = f"{self.api_url}/search/jql"

        async for issues in self._get_paginated_data_using_next_page_token(
            url,
            "issues",
            initial_params=params,
            ignored_errors=self._JQL_IGNORED_ERRORS,
        ):
            yield issues

    async def get_single_user(self, account_id: str) -> dict[str, Any]:
        return await self._send_api_request(
            "GET", f"{self.api_url}/user", params={"accountId": account_id}
        )

    async def get_paginated_users(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting users from Jira")
        async for users in self._get_paginated_data(f"{self.api_url}/users/search"):
            yield users

    async def get_paginated_teams(
        self, org_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting teams from Jira")

        base_url = f"{self.teams_base_url}/{org_id}/teams"

        async for teams in self._get_cursor_paginated_data(
            url=base_url, method="GET", extract_key="entities", cursor_param="cursor"
        ):
            yield teams

    async def get_paginated_team_members(
        self, team_id: str, org_id: str, page_size: int = PAGE_SIZE
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        url = f"{self.teams_base_url}/{org_id}/teams/{team_id}/members"

        async for members in self._get_cursor_paginated_data(
            url,
            method="POST",
            extract_key="results",
            initial_params={"first": page_size},
            cursor_param="after",
        ):
            yield members

    async def fetch_team_members(
        self, team_id: str, org_id: str
    ) -> list[dict[str, Any]]:
        members = []
        async for batch in self.get_paginated_team_members(team_id, org_id):
            members.extend(batch)
        return members

    async def enrich_teams_with_members(
        self, teams: list[dict[str, Any]], org_id: str
    ) -> list[dict[str, Any]]:
        logger.debug(f"Fetching members for {len(teams)} teams")

        team_tasks = [self.fetch_team_members(team["teamId"], org_id) for team in teams]
        results = await asyncio.gather(*team_tasks)

        total_members = sum(len(members) for members in results)
        logger.info(f"Retrieved {total_members} members across {len(teams)} teams")

        for team, members in zip(teams, results):
            team["__members"] = members

        return teams
