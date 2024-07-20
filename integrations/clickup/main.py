from enum import StrEnum
from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from clickup.client import ClickupClient


EVENT_ACTIONS = {
    "listCreated": "register",
    "listUpdated": "register",
    "listDeleted": "unregister",
    "taskCreated": "register",
    "taskUpdated": "register",
    "taskDeleted": "unregister",
}


class ObjectKind(StrEnum):
    TEAM = "team"
    PROJECT = "project"
    ISSUE = "issue"


async def init_client() -> ClickupClient:
    client = ClickupClient(
        ocean.integration_config["clickup_base_url"],
        ocean.integration_config["clickup_personal_token"],
        ocean.integration_config["clickup_archived_parameter"],
    )
    return client


async def setup_application() -> None:
    app_host = ocean.integration_config.get("app_host")
    if not app_host:
        logger.warning(
            "App host was not provided, skipping webhook creation. "
            "Without setting up the webhook, you will have to manually initiate resync to get updates from ClickUp."
        )
        return
    clickup_client = await init_client()  # Await the initialization of the client
    await clickup_client.create_clickup_events_webhook(app_host)


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    clickup_client = await init_client()
    async for teams in clickup_client.get_clickup_teams():
        logger.info(f"Received team of length {len(teams)}")
        yield teams


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    clickup_client = await init_client()
    async for projects in clickup_client.get_folderless_projects():
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_folder_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    clickup_client = await init_client()
    async for projects in clickup_client.get_folder_projects():
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    clickup_client = await init_client()
    async for issues in clickup_client.get_paginated_issues():
        logger.info(f"Received issue batch with {len(issues)} issues")
        yield issues


@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    """
    Handle the webhook request from ClickUp.
    Events are mapped to the appropriate actions in EVENT_ACTIONS.
    """
    clickup_client = await init_client()
    logger.info(f'Received webhook event of type: {data.get("event")}')
    if data.get("event").startswith("list"):
        if EVENT_ACTIONS.get(data.get("event")) == "register":
            project = await clickup_client.get_single_project(data["list_id"])
            await ocean.register_raw(ObjectKind.PROJECT, [project])
        else:
            await ocean.unregister_raw(ObjectKind.PROJECT, [{"id": data["list_id"]}])
    elif data.get("event").startswith("task"):
        if EVENT_ACTIONS.get(data.get("event")) == "register":
            single_issue = await clickup_client.get_single_project(data["task_id"])
            await ocean.register_raw(ObjectKind.ISSUE, [single_issue])
        else:
            await ocean.unregister_raw(ObjectKind.ISSUE, [{"id": data["task_id"]}])
    logger.info("Webhook event processed")
    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean ClickUp integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return
    await setup_application()
