import asyncio
import uuid
from typing import Any, AsyncGenerator, Generator

import httpx
import re
from httpx import Auth, BasicAuth, Request, Response, Timeout
from loguru import logger

from jira.overrides import JiraEpicAPIQueryParams, JiraWorklogAPIQueryParams
from port_ocean.clients.auth.oauth_client import OAuthClient
from port_ocean.context.ocean import ocean
from port_ocean.helpers.async_client import OceanAsyncClient
from .rate_limiter import JiraRateLimiter
from .retry_transport import JiraRetryTransport

PAGE_SIZE = 50
WEBHOOK_NAME = "Port-Ocean-Events-Webhook"
MAX_CONCURRENT_REQUESTS = 10

WORKLOG_WEBHOOK_EVENTS = [
    "worklog_created",
    "worklog_updated",
    "worklog_deleted",
]

WEBHOOK_EVENTS = [
    "jira:issue_created",
    "jira:issue_updated",
    "jira:issue_deleted",
    "jira:version_created",
    "jira:version_updated",
    "jira:version_deleted",
    "jira:version_released",
    "jira:version_unreleased",
    "jira:version_moved",
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
    "board_created",
    "board_updated",
    "board_deleted",
    *WORKLOG_WEBHOOK_EVENTS,
]

OAUTH2_WEBHOOK_EVENTS = [
    "jira:issue_created",
    "jira:issue_updated",
    "jira:issue_deleted",
    "jira:version_created",
    "jira:version_updated",
    "jira:version_deleted",
    "jira:version_released",
    "jira:version_unreleased",
    "jira:version_moved",
    "board_created",
    "board_updated",
    "board_deleted",
    *WORKLOG_WEBHOOK_EVENTS,
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

        # For basic auth, agile URL is known immediately.
        # For OAuth, it requires a cloud ID resolved via API - set in _get_agile_api_url()
        self._agile_api_url: str | None = (
            None if self.is_oauth_enabled() else f"{self.jira_rest_url}/agile/1.0"
        )
        self._software_api_url: str | None = (
            None if self.is_oauth_enabled() else f"{self.jira_rest_url}/software/1.0"
        )

        self._rate_limiter = JiraRateLimiter(max_concurrent=MAX_CONCURRENT_REQUESTS)
        self.client = OceanAsyncClient(
            JiraRetryTransport,
            transport_kwargs={
                "rate_limit_notifier": self._rate_limiter.on_response,
            },
            timeout=Timeout(30),
        )
        self.client.auth = self.jira_api_auth

    def _get_bearer(self) -> BearerAuth:
        try:
            bearer_auth = BearerAuth(self.external_access_token)
            logger.debug(
                "Using external OAuth access token from configured token file for Jira API auth"
            )
            return bearer_auth
        except ValueError:
            logger.warning(
                "OAuth token file was not available; falling back to configured Jira token for bearer auth"
            )
            return BearerAuth(self.jira_token)

    async def _get_agile_api_url(self) -> str:
        """Return the Agile REST API base URL for the current auth scheme.

        For basic auth this is known at construction time.
        For OAuth, the cloud ID must be resolved once via the accessible-resources
        endpoint and the result is cached on the instance.
        """
        if self._agile_api_url is not None:
            return self._agile_api_url

        cloud_id = await self._get_cloud_id()
        self._agile_api_url = (
            f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/agile/latest"
        )
        logger.debug(f"Resolved agile API URL: {self._agile_api_url}")
        return self._agile_api_url

    async def _get_software_api_url(self) -> str:
        """Return the ``software`` REST API base URL for the current auth scheme.

        Used for endpoints migrated away from ``agile``. The ``agile`` equivalents
        are deprecated with removal scheduled for November 1, 2026.
        Ref: https://developer.atlassian.com/cloud/jira/software/changelog/
        """
        if self._software_api_url is not None:
            return self._software_api_url

        cloud_id = await self._get_cloud_id()
        self._software_api_url = (
            f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/software/1.0"
        )
        logger.debug(f"Resolved software API URL: {self._software_api_url}")
        return self._software_api_url

    async def _get_cloud_id(self) -> str:
        """
        Resolve the Atlassian cloud ID for the configured Jira site from jira_url when OAuth gateway format is used,
        otherwise resolve via accessible-resources endpoint.

        See: https://developer.atlassian.com/cloud/oauth/getting-started/making-calls-to-api/#cloud-id
        """
        _ATLASSIAN_GATEWAY_PATTERN = re.compile(
            r"https://api\.atlassian\.com/ex/jira/([^/]+)"
        )
        pattern_match = _ATLASSIAN_GATEWAY_PATTERN.match(self.jira_url.rstrip("/"))
        if pattern_match:
            cloud_id = pattern_match.group(1)
            logger.debug(f"Extracted cloud ID {cloud_id} from jira_url")
            return cloud_id

        resources = await self._send_api_request(
            "GET",
            "https://api.atlassian.com/oauth/token/accessible-resources",
        )
        normalized_jira_url = self.jira_url.rstrip("/")
        for resource in resources:
            if resource.get("url", "").rstrip("/") == normalized_jira_url:
                resolved_id: str = resource.get("id")
                logger.debug(f"Resolved cloud ID {resolved_id} for {self.jira_url}")
                return resolved_id

        raise ValueError(
            f"Could not resolve cloud ID for Jira site '{self.jira_url}'. "
            f"Ensure the configured jira url matches one of the accessible sites "
            f"for this OAuth token."
        )

    def refresh_request_auth_creds(self, request: httpx.Request) -> httpx.Request:
        logger.debug(
            "Refreshing Jira request auth credentials before retry",
            method=request.method,
            url=str(request.url),
        )
        bearer_auth = self._get_bearer()
        # Persist refreshed bearer auth so subsequent new requests use the latest token.
        self.jira_api_auth = bearer_auth
        self.client.auth = bearer_auth
        return next(bearer_auth.auth_flow(request))

    async def _send_api_request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        retryable: bool = False,
    ) -> Any:
        response: httpx.Response | None = None
        try:
            async with self._rate_limiter:
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    headers=headers,
                    extensions={"retryable": retryable} if retryable else None,
                )
                response.raise_for_status()
                await self._rate_limiter.on_response(response)
                return response.json()
        except httpx.HTTPStatusError as e:
            response = e.response
            await self._rate_limiter.on_response(response)
            is_rate_limit = self._rate_limiter.is_rate_limit_response(response)
            logger.bind(
                status_code=response.status_code,
                method=method,
                url=url,
                is_rate_limit=is_rate_limit,
            ).error(
                f"Jira API request failed with status {response.status_code}: {method} {url}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to Jira API: {method} {url} - {str(e)}")
            raise

    async def _get_paginated_data(
        self,
        url: str,
        extract_key: str | None = None,
        initial_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = {**self._generate_base_req_params(), **(initial_params or {})}

        start_at = 0
        while True:
            params["startAt"] = start_at
            response_data = await self._send_api_request("GET", url, params=params)
            items = response_data.get(extract_key, []) if extract_key else response_data

            if not items:
                break

            yield items

            start_at += len(items)

            if "total" in response_data and start_at >= response_data["total"]:
                break

    async def _get_agile_paginated_data(
        self,
        url: str,
        extract_key: str = "values",
        initial_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Paginate Jira Agile REST API endpoints using offset-based pagination."""
        params: dict[str, Any] = {**(initial_params or {})}
        params.setdefault("maxResults", PAGE_SIZE)
        start_at = 0

        while True:
            params["startAt"] = start_at
            response_data = await self._send_api_request("GET", url, params=params)

            items: list[dict[str, Any]] = response_data.get(extract_key, [])

            if not items:
                logger.debug(
                    f"No items returned from {url} at startAt={start_at}, stopping pagination"
                )
                break

            yield items

            is_last = response_data.get("isLast")
            if is_last is True:
                logger.debug(f"Reached last page for {url} at startAt={start_at}")
                break

            if is_last is None and len(items) < params["maxResults"]:
                logger.warning(
                    f"isLast field absent from agile API response at {url}, "
                    f"stopping pagination based on item count ({len(items)} < {params['maxResults']})"
                )
                break

            start_at += len(items)

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

    async def _get_token_paginated_data(
        self,
        url: str,
        extract_key: str,
        initial_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Paginate Jira Software REST API endpoints using GET token-based pagination."""
        query_params: dict[str, Any] = {**(initial_params or {})}
        query_params.setdefault("maxResults", PAGE_SIZE)

        while True:
            response_data = await self._send_api_request(
                "GET", url, params=query_params
            )

            items: list[dict[str, Any]] = response_data.get(extract_key, [])

            if not items:
                break

            yield items

            if response_data.get("isLast") or not (
                next_page_token := response_data.get("nextPageToken")
            ):
                break

            query_params = {**query_params, "nextPageToken": next_page_token}

    @staticmethod
    def _generate_base_req_params(
        maxResults: int = PAGE_SIZE, startAt: int = 0
    ) -> dict[str, Any]:
        return {
            "maxResults": maxResults,
            "startAt": startAt,
        }

    @staticmethod
    def _enrich_with_board_id(
        entities: list[dict[str, Any]], board_id: int
    ) -> list[dict[str, Any]]:
        """Inject ``__boardId`` to each entity in the list for later relation mapping."""
        return [
            {**entity, "__boardId": board_id} for entity in entities if entity.get("id")
        ]

    @staticmethod
    def _validate_existing_webhook(
        webhook: dict[str, Any],
        expected_events: list[str],
        is_oauth: bool,
    ) -> None:
        """Log details and warn about misconfiguration of an existing Jira webhook."""
        logger.info("Ocean real time reporting webhook already exists")
        try:
            jql_filter = (
                webhook.get("jqlFilter")
                if is_oauth
                else (webhook.get("filters") or {}).get("issue-related-events-section")
            )

            if jql_filter:
                if is_oauth:
                    logger.info(f"Existing webhook has a JQL filter: {jql_filter}")
                else:
                    logger.warning(
                        f"Existing webhook has a JQL filter configured on Jira's side, "
                        f"which may prevent some events from being sent. JQL filter: {jql_filter}"
                    )

            actual_events = set(webhook.get("events") or [])
            expected = set(expected_events)
            if actual_events != expected:
                missing = expected - actual_events
                extra = actual_events - expected
                logger.warning(
                    f"Existing webhook events do not match expected events. "
                    f"Missing: {sorted(missing) if missing else 'none'}. "
                    f"Extra: {sorted(extra) if extra else 'none'}"
                )

            if webhook.get("enabled") is False:
                logger.warning(
                    "Existing webhook is disabled and will not fire any events"
                )
        except Exception:
            logger.opt(exception=True).warning(
                "Failed to validate existing webhook configuration"
            )

    async def has_webhook_permission(self) -> bool:
        logger.info(f"Checking webhook permissions for Jira instance: {self.jira_url}")
        response = await self._send_api_request(
            method="GET",
            url=f"{self.api_url}/mypermissions",
            params={"permissions": "ADMINISTER"},
        )
        has_permission = response["permissions"]["ADMINISTER"]["havePermission"]

        return has_permission

    async def _create_events_webhook_oauth(self, app_host: str) -> None:
        webhook_target_app_host = f"{app_host}/integration/webhook"
        webhooks = (await self._send_api_request("GET", url=self.webhooks_url)).get(
            "values"
        )
        if len(webhooks) > 0:
            # jira allows for only one webhook per user per oauth app that is why we are always checking the first webhook
            webhook = webhooks[0]
            existing_webhook_url = webhook.get("url")
            if existing_webhook_url == webhook_target_app_host:
                self._validate_existing_webhook(
                    webhook, OAUTH2_WEBHOOK_EVENTS, is_oauth=True
                )
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

    async def _fetch_backlog_from_software_api(
        self,
        board_id: int,
        params: dict[str, Any],
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch backlog via the ``software`` endpoint."""
        software_url = await self._get_software_api_url()
        url = f"{software_url}/board/{board_id}/backlog"
        async for issue_batch in self._get_token_paginated_data(url, "issues", params):
            yield self._enrich_with_board_id(issue_batch, board_id)

    async def _fetch_backlog_from_agile_api(
        self,
        board_id: int,
        params: dict[str, Any],
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch backlog via the ``agile`` endpoint.

        Deprecated: https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/#api-rest-agile-1-0-board-boardid-backlog-get
        Scheduled for removal: November 1, 2026.
        """
        logger.warning(
            "Fetching backlog via agile API endpoint is deprecated and scheduled for removal by November 1, 2026. Set useSoftwareApi to false only if you need to force legacy behavior for specific boards that are not compatible with the software API endpoint. Please migrate to the software API endpoint as soon as possible."
        )
        agile_url = await self._get_agile_api_url()
        url = f"{agile_url}/board/{board_id}/backlog"
        async for issue_batch in self._get_agile_paginated_data(
            url, "issues", {**params}
        ):
            yield self._enrich_with_board_id(issue_batch, board_id)

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

        for webhook in webhooks:
            if webhook.get("url") == webhook_target_app_host:
                self._validate_existing_webhook(webhook, WEBHOOK_EVENTS, is_oauth=False)
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

    @staticmethod
    def _build_issue_search_body(
        jql: str,
        fields: str | None = None,
        expand: str | None = None,
        reconcile_issues: list[int] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "jql": jql,
            "maxResults": len(reconcile_issues) if reconcile_issues else PAGE_SIZE,
        }
        if fields:
            body["fields"] = (
                ["*all"]
                if fields == "*all"
                else [f.strip() for f in fields.split(",") if f.strip()]
            )
        if expand:
            body["expand"] = expand
        if reconcile_issues:
            body["reconcileIssues"] = reconcile_issues
        return body

    async def _get_paginated_data_using_next_page_token(
        self,
        url: str,
        body: dict[str, Any],
        extract_key: str | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Get paginated data via POST using token-based pagination for JQL endpoints."""
        while True:
            response_data = await self._send_api_request(
                "POST", url, json=body, retryable=True
            )
            items = response_data.get(extract_key, []) if extract_key else response_data

            if not items:
                break

            yield items

            next_page_token = response_data.get("nextPageToken")
            if not next_page_token:
                break

            body = {**body, "nextPageToken": next_page_token}

    async def get_paginated_issues(
        self, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting issues from Jira")
        params = params or {}
        logger.info(f"Using JQL filter: {params['jql']}")
        url = f"{self.api_url}/search/jql"

        body = self._build_issue_search_body(
            jql=params["jql"],
            fields=params.get("fields"),
            expand=params.get("expand"),
            reconcile_issues=params.get("reconcileIssues"),
        )

        async for issues in self._get_paginated_data_using_next_page_token(
            url, body, "issues"
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

    async def get_paginated_versions(
        self, project_key: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield PAGE_SIZE batches of versions for a project, enriched with ``__projectKey``."""
        logger.info("Getting versions from Jira")

        url = f"{self.api_url}/project/{project_key}/version"
        async for versions in self._get_paginated_data(url, "values"):
            for version in versions:
                version["__projectKey"] = project_key
            yield versions

    async def get_single_version(self, version_id: str) -> dict[str, Any]:
        """Fetch a version by ID and enrich it with ``__projectKey``."""
        version = await self._send_api_request(
            "GET", f"{self.api_url}/version/{version_id}"
        )
        if version:
            project_id = version["projectId"]
            project = await self._send_api_request(
                "GET", f"{self.api_url}/project/{project_id}"
            )
            version["__projectKey"] = project["key"]
        return version

    async def get_paginated_boards(
        self, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Fetching boards from Jira")
        resource_base_url = await self._get_agile_api_url()
        endpoint = f"{resource_base_url}/board"

        async for board_batch in self._get_agile_paginated_data(
            endpoint, initial_params=params
        ):
            logger.info(f"Received board batch with {len(board_batch)} boards")
            yield board_batch

    async def get_single_board(self, board_id: int) -> dict[str, Any]:
        """Used by webhook processors to re-fetch board state after board_created or board_updated events."""
        logger.debug(f"Fetching single board: {board_id}")
        resource_base_url = await self._get_agile_api_url()
        return await self._send_api_request(
            "GET", f"{resource_base_url}/board/{board_id}"
        )

    async def get_board_projects(
        self, board_id: int
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch all projects associated with a board.

        A board can be associated with multiple projects when its JQL filter
        references more than one project. Uses the Agile REST API endpoint:
        GET /rest/agile/1.0/board/{boardId}/project
        """
        agile_url = await self._get_agile_api_url()
        async for project_batch in self._get_agile_paginated_data(
            url=f"{agile_url}/board/{board_id}/project",
        ):
            yield project_batch

    async def enrich_board_with_projects(self, board: dict[str, Any]) -> dict[str, Any]:
        """Enrich a board with all associated project keys.

        Fetches all projects for the board and injects __projectKeys
        as a list for relation mapping.

        Args:
            board: The raw board object from the list endpoint.
        """
        board_id = board.get("id")
        if board_id is None:
            logger.warning("Board is missing id field, skipping project enrichment")
            board["__projectKeys"] = []
            return board

        project_keys: list[str] = []

        async for project_batch in self.get_board_projects(board_id):
            project_keys.extend(
                project["key"] for project in project_batch if project.get("key")
            )

        board["__projectKeys"] = project_keys
        return board

    async def get_paginated_backlog_for_board(
        self,
        board_id: int,
        jql: str | None = None,
        fields: list[str] | None = None,
        *,
        use_software_api: bool = True,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """
        Fetch backlog issues for a board with optional JQL filter and field selection.

        Defaults to the ``software`` endpoint, the post-deprecation path for
        backlog retrieval. Set ``use_software_api=False`` to fall back to the legacy
        ``agile`` endpoint, which is scheduled for removal on November 1, 2026.
        """
        logger.info(
            f"Fetching backlog for board {board_id}. "
            f"use_software_api={use_software_api})"
        )

        query_params: dict[str, Any] = {}
        if jql:
            query_params["jql"] = jql
        if fields is not None:
            query_params["fields"] = ",".join(fields)

        if not use_software_api:
            async for backlogs in self._fetch_backlog_from_agile_api(
                board_id, query_params
            ):
                yield backlogs
            return

        try:
            async for backlogs in self._fetch_backlog_from_software_api(
                board_id, query_params
            ):
                yield backlogs
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                try:
                    error_messages = e.response.json().get("errorMessages", [])
                    detail = "; ".join(error_messages) if error_messages else "no details"
                except Exception:
                    detail = "no details"
                logger.warning(
                    f"Board {board_id} returned 400, skipping.\nDetails: {detail}"
                )
                return
            raise

    async def get_paginated_epics_for_board(
        self,
        board_id: int,
        api_params: JiraEpicAPIQueryParams | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield epic batches for a board, filtered by completion status.

        Epic retrieval is per-board. The done query param is optional:
        - done='false' (default) — incomplete epics only, protects large instances
          from pulling full epic history on first install
        - done='true' — completed epics only
        - done=None — omits the param entirely, fetches all epics

        See: https://developer.atlassian.com/cloud/jira/software/rest/api-group-board/
        #api-rest-agile-1-0-board-boardid-epic-get
        """
        agile_url = await self._get_agile_api_url()
        url = f"{agile_url}/board/{board_id}/epic"

        query_params: dict[str, Any] = {}
        if api_params and api_params.done is not None:
            query_params["done"] = api_params.done

        async for epic_batch in self._get_agile_paginated_data(
            url=url,
            initial_params=query_params,
        ):
            for epic in epic_batch:
                epic["__boardId"] = board_id
            yield epic_batch

    async def get_single_epic(
        self,
        epic_id_or_key: int | str,
    ) -> dict[str, Any]:
        """Fetch a single epic by numeric ID or Jira issue key.

        Accepts both formats per the Jira Agile API contract:
        - Numeric ID: 17022
        - Issue key: EXAMPLEISSUE-6459

        See: https://developer.atlassian.com/cloud/jira/software/rest/api-group-epic/
        #api-rest-agile-1-0-epic-epicidorkey-get
        """
        agile_url = await self._get_agile_api_url()
        return await self._send_api_request(
            "GET",
            f"{agile_url}/epic/{epic_id_or_key}",
        )

    async def get_paginated_worklogs_for_issue(
        self,
        issue_key: str,
        api_params: JiraWorklogAPIQueryParams | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch worklogs for a single issue."""
        url = f"{self.api_url}/issue/{issue_key}/worklog"

        query_params: dict[str, Any] = {}
        if api_params:
            if api_params.started_after is not None:
                query_params["startedAfter"] = api_params.started_after
            if api_params.started_before is not None:
                query_params["startedBefore"] = api_params.started_before
            if api_params.expand:
                query_params["expand"] = api_params.expand

        async for batch in self._get_paginated_data(
            url, "worklogs", initial_params=query_params
        ):
            yield [{**worklog, "__issueKey": issue_key} for worklog in batch]
