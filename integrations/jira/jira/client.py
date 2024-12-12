import typing
from typing import Any, AsyncGenerator, Generator, List, Dict, Optional

from httpx import Timeout, Auth, BasicAuth, Request, Response
from jira.overrides import JiraResourceConfig
from loguru import logger

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client

PAGE_SIZE = 50
WEBHOOK_NAME = "Port-Ocean-Events-Webhook"

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


class BearerAuth(Auth):
    def __init__(self, token: str):
        self.token = token

    def auth_flow(self, request: Request) -> Generator[Request, Response, None]:
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request


class JiraClient:
    jira_api_auth: Auth

    def __init__(self, jira_url: str, jira_email: str, jira_token: str) -> None:
        self.jira_url = jira_url
        self.jira_rest_url = f"{self.jira_url}/rest"
        self.jira_email = jira_email
        self.jira_token = jira_token

        # If the Jira URL is directing to api.atlassian.com, we use OAuth2 Bearer Auth
        if "api.atlassian.com" in self.jira_url:
            self.jira_api_auth = BearerAuth(self.jira_token)
        else:
            self.jira_api_auth = BasicAuth(self.jira_email, self.jira_token)

        self.api_url = f"{self.jira_rest_url}/api/3"
        self.webhooks_url = f"{self.jira_rest_url}/webhooks/1.0/webhook"

        self.client = http_async_client
        self.client.auth = self.jira_api_auth
        self.client.timeout = Timeout(30)

    async def _send_api_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        response = await self.client.request(
            method=method, url=url, params=params, json=json, headers=headers
        )
        response.raise_for_status()
        return response.json()

    async def _get_paginated_data(
        self,
        url: str,
        extract_key: Optional[str] = None,
        page_size: int = PAGE_SIZE,
        initial_params: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Generic method for handling paginated requests."""
        params = initial_params or {}
        params.update(self._generate_base_req_params())
        params["maxResults"] = page_size

        start_at = 0
        while True:
            params["startAt"] = start_at
            response_data = await self._send_api_request("GET", url, params=params)

            if extract_key:
                items = response_data.get(extract_key, [])
            else:
                items = response_data if isinstance(response_data, list) else [response_data]

            if not items:
                break

            yield items

            start_at += page_size

            if "total" in response_data and start_at >= response_data["total"]:
                break

    async def _get_cursor_paginated_data(
        self,
        url: str,
        method: str,
        extract_key: Optional[str] = None,
        page_size: int = PAGE_SIZE,
        initial_params: Optional[Dict[str, Any]] = None,
        cursor_param: str = "cursor",
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        """Handle cursor-based pagination for specific endpoint."""
        params = initial_params or {}
        cursor = params.get(cursor_param)

        while True:
            if cursor:
                params[cursor_param] = cursor

            response_data = await self._send_api_request(method, url, params=params)

            items = (response_data.get(extract_key, []) if extract_key 
                else ([response_data] if isinstance(response_data, dict) else response_data))

            if not items:
                break

            yield items

            page_info = response_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            cursor = page_info.get("endCursor")

            if not has_next_page:
                break
    @staticmethod
    def _generate_base_req_params(
        maxResults: int = 0, startAt: int = 0
    ) -> Dict[str, Any]:
        return {
            "maxResults": maxResults,
            "startAt": startAt,
        }
    async def _get_webhooks(self) -> List[Dict[str, Any]]:
        response = await self.client.request(method="GET", url=self.webhooks_url)
        response.raise_for_status()
        return response.json()

    async def create_events_webhook(self, app_host: str) -> None:
        webhook_target_app_host = f"{app_host}/integration/webhook"
        webhook_check = await self._get_webhooks() 

        for webhook in webhook_check:
            if webhook["url"] == webhook_target_app_host:
                logger.info("Ocean real time reporting webhook already exists")
                return

        body = {
            "name": f"{ocean.config.integration.identifier}-{WEBHOOK_NAME}",
            "url": webhook_target_app_host,
            "events": WEBHOOK_EVENTS,
        }

        await self._send_api_request("POST", self.webhooks_url, json=body)
        logger.info("Ocean real time reporting webhook created")

    async def get_single_project(self, project_key: str) -> Dict[str, Any]:
        return await self._send_api_request(
            "GET", f"{self.api_url}/project/{project_key}"
        )

    async def get_paginated_projects(
        self,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.info("Getting projects from Jira")
        async for projects in self._get_paginated_data(
            f"{self.api_url}/project/search", "values"
        ):
            yield projects

    async def get_single_issue(self, issue_key: str) -> Dict[str, Any]:
        return await self._send_api_request("GET", f"{self.api_url}/issue/{issue_key}")

    async def get_paginated_issues(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.info("Getting issues from Jira")

        config = typing.cast(JiraResourceConfig, event.resource_config)
        params = {}
        if config.selector.jql:
            params["jql"] = config.selector.jql
            logger.info(f"Found JQL filter: {config.selector.jql}")

        async for issues in self._get_paginated_data(
            f"{self.api_url}/search", "issues", initial_params=params
        ):
            yield issues

    async def get_single_user(self, account_id: str) -> Dict[str, Any]:
        return await self._send_api_request(
            "GET", f"{self.api_url}/user", params={"accountId": account_id}
        )

    async def get_paginated_users(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.info("Getting users from Jira")
        async for users in self._get_paginated_data(f"{self.api_url}/users/search"):
            yield users

    async def get_paginated_teams(self) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.info("Getting teams from Jira")

        org_id = ocean.integration_config["atlassian_organisation_id"]
        base_url = f"https://admin.atlassian.com/gateway/api/public/teams/v1/org/{org_id}/teams"

        cursor = None
        while True:
            params: Dict[str, Any] = {}
            if cursor:
                params["cursor"] = cursor

            teams_data = await self._send_api_request("GET", base_url, params=params)

            if not teams_data["entities"]:
                break

            logger.info(f"Retrieved {len(teams_data['entities'])} teams")
            yield teams_data["entities"]

            cursor = teams_data.get("cursor")
            if not cursor:
                break

    async def get_paginated_team_members(
        self, team_id: str, page_size: int = 40
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        logger.info(f"Getting members for team {team_id}")
        org_id = ocean.integration_config["atlassian_organisation_id"]
        url = f"{self.jira_url}/gateway/api/public/teams/v1/org/{org_id}/teams/{team_id}/members"

        async for members in self._get_cursor_paginated_data(
            url,
            method="POST",
            extract_key="results",
            page_size=page_size,
            initial_params={"first": page_size},
            cursor_param="after",
        ):
            logger.info(f"Retrieved {len(members)} members for team {team_id}")
            yield members

    async def get_user_team_mapping(self) -> Dict[str, str]:

        user_team_mapping = {}

        teams = []
        async for team_batch in self.get_paginated_teams():
            teams.extend(team_batch)

        logger.info(f"Processing {len(teams)} teams for user mapping")

        for team in teams:
            team_id = team["teamId"]
            async for members in self.get_paginated_team_members(team_id):
                for member in members:
                    account_id = member["accountId"]
                    if account_id not in user_team_mapping:
                        user_team_mapping[account_id] = team_id

        logger.info(f"Created mapping for {len(user_team_mapping)} users")
        return user_team_mapping

    async def enrich_users_with_teams(self, users: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        users_to_process = [user for user in users if "teamId" not in user]

        if not users_to_process:
            return users

        logger.info(f"Enriching {len(users_to_process)} users with team information")

        user_team_mapping = await self.get_user_team_mapping()

        for user in users_to_process:
            account_id = user["accountId"]
            if account_id in user_team_mapping:
                user["teamId"] = user_team_mapping[account_id]

        return users
