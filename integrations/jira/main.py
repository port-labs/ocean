import typing
from enum import StrEnum
from typing import Any, cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from jira.client import JiraClient
from jira.overrides import (
    JiraIssueConfig,
    JiraProjectResourceConfig,
    TeamResourceConfig,
)


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"
    USER = "user"
    TEAM = "team"


def create_jira_client() -> JiraClient:
    """Create JiraClient with current configuration."""
    return JiraClient(
        ocean.integration_config["jira_host"],
        ocean.integration_config["atlassian_user_email"],
        ocean.integration_config["atlassian_user_token"],
    )


async def setup_application() -> None:
    base_url = ocean.app.base_url
    if not base_url:
        return

    client = create_jira_client()
    await client.create_events_webhook(base_url)


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_client()

    selector = cast(JiraProjectResourceConfig, event.resource_config).selector
    params = {"expand": selector.expand}

    async for projects in client.get_paginated_projects(params):
        logger.info(f"Received project batch with {len(projects)} issues")
        yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_client()

    params = {}
    config = typing.cast(JiraIssueConfig, event.resource_config)

    if config.selector.jql:
        params["jql"] = config.selector.jql
        logger.info(
            f"Found JQL filter: {config.selector.jql}... Adding to request param"
        )

    if config.selector.fields:
        params["fields"] = config.selector.fields

    async for issues in client.get_paginated_issues(params):
        logger.info(f"Received issue batch with {len(issues)} issues")
        yield issues


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_client()
    org_id = ocean.integration_config.get("atlassian_organization_id")

    if not org_id:
        logger.warning(
            "Atlassian organization ID wasn't specified, unable to sync teams, skipping"
        )
        return

    selector = cast(TeamResourceConfig, event.resource_config).selector
    async for teams in client.get_paginated_teams(org_id):
        logger.info(f"Received team batch with {len(teams)} teams")
        if selector.include_members:
            teams = await client.enrich_teams_with_members(teams, org_id)
        yield teams


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_client()

    async for users_batch in client.get_paginated_users():
        logger.info(f"Received users batch with {len(users_batch)} users")
        yield users_batch

class JiraProjectWebhookProcessor(AbstractWebhookProcessor):
    def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent", "").startswith("project_")

    def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PROJECT]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        # For Jira webhooks, we don't need additional authentication as they are validated
        # through the webhook secret in the URL
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        # Validate that the payload contains the required fields
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        webhook_event = payload.get("webhookEvent")
        if not webhook_event:
            logger.error("Missing webhook event")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        client = create_jira_client()
        project_key = payload["project"]["key"]

        if webhook_event == "project_soft_deleted":
            logger.info(f"Project {project_key} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[payload["project"]],
            )

        logger.debug(f"Fetching project with key: {project_key}")
        item = await client.get_single_project(project_key)

        if not item:
            logger.warning(f"Failed to retrieve {ObjectKind.PROJECT}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        data_to_update = []
        data_to_delete = []
        logger.debug(f"Retrieved {ObjectKind.PROJECT} item: {item}")

        if "deleted" in webhook_event:
            data_to_delete.extend([item])
        else:
            data_to_update.extend([item])

        return WebhookEventRawResults(
            updated_raw_results=data_to_update,
            deleted_raw_results=data_to_delete,
        )

class JiraUserWebhookProcessor(AbstractWebhookProcessor):
    def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent", "").startswith("user_")

    def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.USER]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        # For Jira webhooks, we don't need additional authentication as they are validated
        # through the webhook secret in the URL
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        # Validate that the payload contains the required fields
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        webhook_event = payload.get("webhookEvent")

        if not webhook_event:
            logger.error("Missing webhook event")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        client = create_jira_client()
        account_id = payload["user"]["accountId"]
        logger.debug(f"Fetching user with accountId: {account_id}")
        item = await client.get_single_user(account_id)

        if not item:
            logger.warning(f"Failed to retrieve {ObjectKind.USER}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        data_to_update = []
        data_to_delete = []
        logger.debug(f"Retrieved {ObjectKind.USER} item: {item}")

        if "deleted" in webhook_event:
            data_to_delete.extend([item])
        else:
            data_to_update.extend([item])

        return WebhookEventRawResults(
            updated_raw_results=data_to_update,
            deleted_raw_results=data_to_delete,
        )


class JiraIssueWebhookProcessor(AbstractWebhookProcessor):
    def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent", "").startswith("jira:issue_")

    def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE]


    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = create_jira_client()
        issue_key = payload["issue"]["key"]
        logger.info(
            f"Fetching issue with key: {issue_key} and applying specified JQL filter"
        )

        if payload.get("webhookEvent") == "jira:issue_deleted":
            logger.info(f"Issue {issue_key} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[payload["issue"]],
            )

        params = {}

        if resource_config.selector.jql:
            params["jql"] = (
                f"{resource_config.selector.jql} AND key = {payload['issue']['key']}"
            )
        else:
            params["jql"] = f"key = {payload['issue']['key']}"

        issues: list[dict[str, Any]] = []
        async for issues_batch in client.get_paginated_issues(params):
            issues.extend(issues_batch)

        data_to_update = []
        data_to_delete = []
        if not issues:
            logger.warning(
                f"Issue {payload['issue']['key']} not found"
                f" using the following query: {params['jql']},"
                " trying to remove..."
            )
            data_to_delete.append(payload["issue"])
        else:
            data_to_update.extend(issues)

        return WebhookEventRawResults(
            updated_raw_results=data_to_update,
            deleted_raw_results=data_to_delete,
        )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        # For Jira webhooks, we don't need additional authentication as they are validated
        # through the webhook secret in the URL
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        # Validate that the payload contains the required fields
        return True

# Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Jira integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    await setup_application()


ocean.add_webhook_processor("/webhook", JiraIssueWebhookProcessor)
ocean.add_webhook_processor("/webhook", JiraProjectWebhookProcessor)
ocean.add_webhook_processor("/webhook", JiraUserWebhookProcessor)
