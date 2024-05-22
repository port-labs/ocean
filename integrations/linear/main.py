from enum import StrEnum
from typing import Any

from loguru import logger
from linear.client import LinearClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    TEAM = "team"
    LABEL = "label"
    ISSUE = "issue"


async def setup_application() -> None:
    logic_settings = ocean.integration_config
    app_host = logic_settings.get("app_host")
    if not app_host:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Linear"
        )
        return

    linear_client = LinearClient(logic_settings["linear_api_key"])

    await linear_client.create_events_webhook(
        logic_settings["app_host"],
    )


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LinearClient(ocean.integration_config["linear_api_key"])

    async for teams in client.get_paginated_teams():
        logger.info(f"Received team batch with {len(teams)} teams")
        yield teams


@ocean.on_resync(ObjectKind.LABEL)
async def on_resync_labels(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LinearClient(ocean.integration_config["linear_api_key"])

    async for labels in client.get_paginated_labels():
        logger.info(f"Received label batch with {len(labels)} labels")
        yield labels


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = LinearClient(ocean.integration_config["linear_api_key"])

    async for issues in client.get_paginated_issues():
        logger.info(f"Received issue batch with {len(issues)} issues")
        yield issues


@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    client = LinearClient(ocean.integration_config["linear_api_key"])
    logger.info(
        f'Received webhook event of type: {data.get("action")} {data.get("type")}'
    )
    if "type" in data:
        if data["type"] == "Issue":
            logger.info(
                f'Received webhook event for issue: {data["data"]["identifier"]}'
            )
            issue = await client.get_single_issue(data["data"]["identifier"])
            logger.debug(issue)
            await ocean.register_raw(ObjectKind.ISSUE, [issue])
        elif data["type"] == "IssueLabel":
            logger.info(
                f'Received webhook event for label with ID: {data["data"]["id"]} and name: {data["data"]["name"]}'
            )
            label = await client.get_single_label(data["data"]["id"])
            logger.debug(label)
            await ocean.register_raw(ObjectKind.LABEL, [label])
    logger.info("Webhook event processed")
    return {"ok": True}


# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Linear integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    await setup_application()
