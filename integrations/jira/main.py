import asyncio
from typing import cast, Any

from loguru import logger
from initialize_client import create_jira_client
from kinds import Kinds
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from webhook_processors.board_webhook_processor import BoardWebhookProcessor

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from jira.overrides import (
    JiraIssueConfig,
    JiraProjectResourceConfig,
    TeamResourceConfig,
    JiraBoardResourceConfig,
)
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.project_webhook_processor import ProjectWebhookProcessor
from webhook_processors.user_webhook_processor import UserWebhookProcessor
from webhook_processors.version_webhook_processor import VersionWebhookProcessor


async def setup_application() -> None:
    base_url = ocean.app.base_url
    if not base_url:
        return

    client = create_jira_client()
    await client.create_webhooks(base_url)


@ocean.on_resync(Kinds.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_client()

    selector = cast(JiraProjectResourceConfig, event.resource_config).selector
    params = {"expand": selector.expand}

    async for projects in client.get_paginated_projects(params):
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects


@ocean.on_resync(Kinds.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_client()

    params = {}
    config = cast(JiraIssueConfig, event.resource_config)

    jql = config.selector.jql.strip() if config.selector.jql else ""
    params["jql"] = jql
    logger.info(f"Using JQL filter: {jql}")

    if config.selector.fields:
        params["fields"] = config.selector.fields
    if config.selector.expand:
        params["expand"] = config.selector.expand
    async for issues in client.get_paginated_issues(params):
        logger.info(f"Received issue batch with {len(issues)} issues")
        yield issues


@ocean.on_resync(Kinds.TEAM)
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


@ocean.on_resync(Kinds.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_client()

    async for users_batch in client.get_paginated_users():
        logger.info(f"Received users batch with {len(users_batch)} users")
        yield users_batch


@ocean.on_resync(Kinds.RELEASE)
async def on_resync_releases(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_client()

    async for projects in client.get_paginated_projects():
        logger.info(f"Fetching versions for {len(projects)} projects concurrently")
        version_streams = [
            client.get_paginated_versions(project["key"]) for project in projects
        ]
        async for version_batch in stream_async_iterators_tasks(*version_streams):
            yield version_batch


@ocean.on_resync(Kinds.BOARD)
async def on_resync_boards(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_client()
    selector = cast(JiraBoardResourceConfig, event.resource_config).selector

    params: dict[str, Any] = {}
    if selector.board_type is not None:
        params["type"] = selector.board_type
    if selector.project_key is not None:
        params["projectKeyOrId"] = selector.project_key

    async for board_batch in client.get_paginated_boards(params):
        enriched_boards = await asyncio.gather(
            *[client.enrich_board_with_projects(board) for board in board_batch]
        )
        logger.info(f"Received board batch with {len(board_batch)} boards")
        yield list(enriched_boards)


# Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Jira integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    await setup_application()


ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
ocean.add_webhook_processor("/webhook", ProjectWebhookProcessor)
ocean.add_webhook_processor("/webhook", UserWebhookProcessor)
ocean.add_webhook_processor("/webhook", VersionWebhookProcessor)
ocean.add_webhook_processor("/webhook", BoardWebhookProcessor)
