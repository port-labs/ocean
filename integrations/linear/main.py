from loguru import logger
from linear.client import LinearClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from kinds import ObjectKind
from webhook_processors import LabelWebhookProcessor, IssueWebhookProcessor


async def setup_application() -> None:
    base_url = ocean.app.base_url
    if not base_url:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Linear"
        )
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
