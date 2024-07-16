from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import RAW_RESULT, ASYNC_GENERATOR_RESYNC_TYPE
from client import ClickUpClient
from typing import Any
from enum import StrEnum


class ObjectKind(StrEnum):
    TEAM = "team"
    PROJECT = "project"
    ISSUE = "issue"


def init_client() -> ClickUpClient:
    """Initialize ClickUp client with the integration token."""
    return ClickUpClient(
        clickup_token=ocean.integration_config["clickup_token"],
        host=ocean.integration_config["clickup_host"],
    )


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> RAW_RESULT:
    client = init_client()
    teams = await client.get_teams()
    logger.info(f"Received {len(teams)} teams from clickUp")
    return teams


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> RAW_RESULT:
    client = init_client()
    projects = await client.get_spaces()
    logger.info(f"Received {len(projects)} projects")
    return projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    async for issues in client.get_paginated_tasks():
        logger.info(f"Received task batch with {len(issues)} tasks")
        yield issues


@ocean.router.post("/webhook")
async def handle_webhook(data: dict[str, Any]) -> dict[str, Any]:
    client = init_client()
    logger.warning(f"Received {len(data)} webhooks")
    event_handlers = {
        "task": (ObjectKind.ISSUE, client.get_task),
        "team": (ObjectKind.TEAM, client.get_team),
        "space": (ObjectKind.PROJECT, client.get_space),
    }
    for key, (kind, handler) in event_handlers.items():
        if key in data["event"]:
            logger.warning(f"Received {key} webhook")
            entity = await handler(data["task_id"])
            await ocean.register_raw(kind, [entity])
            logger.info(f"Webhook event processed for {kind.value}")
    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    if not ocean.integration_config.get("app_host"):
        logger.warning(
            "No app host provided, skipping webhook creation."
            "Without setting up the webhook, the integration will not export live changes from ClickUp"
        )
        return

    client = init_client()
    team_id = (await client.get_teams())[0]["id"]

    webhooks = await client.get_webhooks(team_id)
    webhook_target_url = f"{ocean.integration_config['app_host']}/integration/webhook"
    webhook_exists = any(
        config["endpoint"] == webhook_target_url for config in webhooks
    )
    if webhook_exists:
        logger.info("Webhook already exists")
    else:
        await client.create_webhook(team_id, ocean.integration_config["app_host"])
