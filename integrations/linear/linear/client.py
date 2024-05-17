from enum import StrEnum
from typing import Any, AsyncGenerator, Optional

from httpx import Timeout

from loguru import logger
import jinja2
from linear.queries import QUERIES

from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client


class LinearObject(StrEnum):
    TEAMS = "TEAMS"
    LABELS = "LABELS"
    ISSUES = "ISSUES"


PAGE_SIZE = 50
WEBHOOK_NAME = "Port-Ocean-Events-Webhook"

WEBHOOK_EVENTS = [
    "Issue",
    "IssueLabel",
]


class LinearClient:
    def __init__(self, linear_api_key: str) -> None:
        self.linear_url = "https://api.linear.app/graphql"
        self.linear_api_key = linear_api_key

        self.api_auth_header = {"Authorization": self.linear_api_key}
        self.client = http_async_client
        self.client.headers.update(self.api_auth_header)
        self.client.timeout = Timeout(30)

    async def _get_paginated_objects(
        self, object_type: str, page_size: int, end_cursor: Optional[str]
    ) -> dict[str, Any]:
        if end_cursor:
            template = jinja2.Template(
                QUERIES[f"GET_NEXT_{object_type}_PAGE"], enable_async=True
            )
            query = await template.render_async(
                page_size=page_size, end_cursor=end_cursor
            )
        else:
            template = jinja2.Template(
                QUERIES[f"GET_FIRST_{object_type}_PAGE"], enable_async=True
            )
            query = await template.render_async(page_size=page_size)
        logger.debug(f"{object_type} query: {query}")
        response = await self.client.post(self.linear_url, json={"query": query})
        response.raise_for_status()
        return response.json()

    async def create_events_webhook(self, app_host: str) -> None:
        webhook_target_app_host = f"{app_host}/integration/webhook"
        logger.debug(f"Webhook check query: {QUERIES['GET_LIVE_EVENTS_WEBHOOKS']}")
        webhook_check_response = await self.client.post(
            self.linear_url, json={"query": QUERIES["GET_LIVE_EVENTS_WEBHOOKS"]}
        )
        webhook_check_response.raise_for_status()
        webhook_check = webhook_check_response.json()

        for webhook in webhook_check["data"]["webhooks"]["nodes"]:
            if webhook["url"] == webhook_target_app_host:
                logger.info("Ocean real time reporting webhook already exists")
                return

        template = jinja2.Template(
            QUERIES[f"CREATE_LIVE_EVENTS_WEBHOOK"], enable_async=True
        )
        query = await template.render_async(
            webhook_label=f"{ocean.config.integration.identifier}-{WEBHOOK_NAME}",
            webhook_url=webhook_target_app_host,
            resource_types=WEBHOOK_EVENTS,
        )
        logger.debug(f"Webhook create query: {query}")
        webhook_create_response = await self.client.post(
            self.linear_url, json={"query": query}
        )
        webhook_create_response.raise_for_status()
        logger.info("Ocean real time reporting webhook created")

    async def get_paginated_teams(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting teams from Linear")

        has_next_page = True
        end_cursor = None
        while has_next_page:
            team_response_list = await self._get_paginated_objects(
                LinearObject.TEAMS, PAGE_SIZE, end_cursor
            )
            # Response format is: { data: { teams: { edges: [ { cursor: "...", node: {...} } ] } } }
            # yielding { node: {...} } for mapping consistency
            yield team_response_list["data"]["teams"]["edges"]
            has_next_page = team_response_list["data"]["teams"]["pageInfo"][
                "hasNextPage"
            ]
            end_cursor = team_response_list["data"]["teams"]["pageInfo"]["endCursor"]

    async def get_paginated_labels(
        self,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting labels from Linear")

        has_next_page = True
        end_cursor = None
        while has_next_page:
            label_response_list = await self._get_paginated_objects(
                LinearObject.LABELS, PAGE_SIZE, end_cursor
            )
            # Response format is: { data: { issueLabels: { edges: [ { cursor: "...", node: {...} } ] } } }
            # yielding { node: {...} } for mapping consistency
            yield label_response_list["data"]["issueLabels"]["edges"]
            has_next_page = label_response_list["data"]["issueLabels"]["pageInfo"][
                "hasNextPage"
            ]
            end_cursor = label_response_list["data"]["issueLabels"]["pageInfo"][
                "endCursor"
            ]

    async def get_paginated_issues(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting issues from Linear")

        has_next_page = True
        end_cursor = None
        while has_next_page:
            issue_response_list = await self._get_paginated_objects(
                LinearObject.ISSUES, PAGE_SIZE, end_cursor
            )
            # Response format is: { data: { issues: { edges: [ { cursor: "...", node: {...} } ] } } }
            # yielding { node: {...} } for mapping consistency
            yield issue_response_list["data"]["issues"]["edges"]
            has_next_page = issue_response_list["data"]["issues"]["pageInfo"][
                "hasNextPage"
            ]
            end_cursor = issue_response_list["data"]["issues"]["pageInfo"]["endCursor"]

    async def get_single_issue(self, issue_identifier: str) -> dict[str, Any]:
        logger.info(f"Querying single issue: {issue_identifier}")
        template = jinja2.Template(QUERIES["GET_SINGLE_ISSUE"], enable_async=True)
        query = await template.render_async(issue_identifier=issue_identifier)
        logger.debug(f"Query: {query}")
        issue_response = await self.client.post(self.linear_url, json={"query": query})
        issue_response.raise_for_status()
        # Response format is: { data: { issue: {...} } }
        # Changing to { node: {...} } for mapping consistency
        issue_json = issue_response.json()
        issue_json["node"] = issue_json["data"]["issue"]
        del issue_json["data"]
        return issue_json

    async def get_single_label(self, label_id: str) -> dict[str, Any]:
        logger.info(f"Querying single label: {label_id}")
        template = jinja2.Template(QUERIES["GET_SINGLE_LABEL"], enable_async=True)
        query = await template.render_async(label_id=label_id)
        logger.debug(f"Query: {query}")
        label_response = await self.client.post(self.linear_url, json={"query": query})
        label_response.raise_for_status()
        # Response format is: { data: { issueLabel: {...} } }
        # Changing to { node: {...} } for mapping consistency
        label_json = label_response.json()
        label_json["node"] = label_json["data"]["issueLabel"]
        del label_json["data"]
        return label_json
