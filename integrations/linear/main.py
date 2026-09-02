from loguru import logger
from typing import cast

from linear.client import LinearClient
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from linear.utils import ObjectKind
from webhook_processors import (
    DocumentWebhookProcessor,
    IssueWebhookProcessor,
    LabelWebhookProcessor,
)


async def setup_application() -> None:
    base_url = ocean.app.base_url
    if not base_url:
        return

    linear_client = LinearClient.create_from_ocean_configuration()
    await linear_client.create_events_webhook(base_url)


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LinearClient.create_from_ocean_configuration()

    async for teams in client.get_paginated_teams():
        logger.info(f"Received team batch with {len(teams)} teams")
        yield teams


@ocean.on_resync(ObjectKind.LABEL)
async def on_resync_labels(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LinearClient.create_from_ocean_configuration()

    async for labels in client.get_paginated_labels():
        logger.info(f"Received label batch with {len(labels)} labels")
        yield labels


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LinearClient.create_from_ocean_configuration()

    async for issues in client.get_paginated_issues():
        logger.info(f"Received issue batch with {len(issues)} issues")
        yield issues


@ocean.on_resync(ObjectKind.DOCUMENT)
async def on_resync_documents(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LinearClient.create_from_ocean_configuration()

    async for documents in client.get_paginated_documents():
        logger.info(f"Received document batch with {len(documents)} documents")
        yield documents


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LinearClient.create_from_ocean_configuration()

    async for users in client.get_paginated_users():
        logger.info(f"Received user batch with {len(users)} users")
        yield users


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LinearClient.create_from_ocean_configuration()

    async for projects in client.get_paginated_projects():
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects


@ocean.on_resync(ObjectKind.TEAM_MEMBERS)
async def on_resync_team_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LinearClient.create_from_ocean_configuration()

    async for team_members in client.get_paginated_team_members():
        logger.info(f"Received team member batch with {len(team_members)} memberships")
        yield team_members


@ocean.on_resync(ObjectKind.CYCLE)
async def on_resync_cycles(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LinearClient.create_from_ocean_configuration()

    async for cycles in client.get_paginated_cycles():
        logger.info(f"Received cycle batch with {len(cycles)} cycles")
        yield cycles

# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Linear integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    await setup_application()


ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
ocean.add_webhook_processor("/webhook", LabelWebhookProcessor)
ocean.add_webhook_processor("/webhook", DocumentWebhookProcessor)
