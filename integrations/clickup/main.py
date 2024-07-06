from enum import StrEnum
from loguru import logger
from typing import Any

from clickup.client import ClickupClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_RESULT


class ObjectKind(StrEnum):
    TEAM = "team"
    PROJECT = "project"
    ISSUE = "issue"


def create_client() -> ClickupClient:
    return ClickupClient(ocean.integration_config["clickup_personal_token"])


async def setup_application() -> None:
    config = ocean.integration_config
    app_host = config.get("app_host")
    if not app_host:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Clickup"
        )
        return

    client = create_client()
    await client.create_webhook_events(app_host)


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> RAW_RESULT:
    client = create_client()

    teams = await client.get_teams()
    logger.info(f"Received team batch with {len(teams)} teams")
    return teams


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> RAW_RESULT:
    client = create_client()

    projects = await client.get_projects()
    logger.info(f"Received project batch with {len(projects)} projects")
    return projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_client()

    async for issues in client.get_paginated_issues():
        logger.info(f"Received issue batch with {len(issues)} issues")
        yield issues


@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    client = create_client()

    event: str = data.get("event", "")
    logger.info(f"Received clickup webhook event: {event}")

    if event.startswith("list"):
        logger.info(f"Received webhook project event: {data['list_id']}")
        project = await client.get_single_project(data["list_id"])

        if event.endswith("Deleted"):
            await ocean.unregister_raw(ObjectKind.PROJECT, [project])
        else:
            await ocean.register_raw(ObjectKind.PROJECT, [project])
    elif event.startswith("task"):
        logger.info(f"Received webhook task event: {data['task_id']}")
        issue = await client.get_single_issue(data["task_id"])

        if event.endswith("Deleted"):
            await ocean.unregister_raw(ObjectKind.ISSUE, [issue])
        else:
            await ocean.register_raw(ObjectKind.ISSUE, [issue])

    logger.info("Webhook event processed")
    return {"status": "ok"}


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Clickup integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    await setup_application()
