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
    Events are mapped to the appropriate actions in event_handlers.
    """
    clickup_client = await init_client()
    logger.info(f"Received webhook event of type: {data.get('event')}")
    event_handlers = {
        "task": (ObjectKind.ISSUE, clickup_client.get_single_issue),
        "list": (ObjectKind.PROJECT, clickup_client.get_single_project),
    }
    event_type = data["event"]
    action = "unregister" if "Deleted" in event_type else "register"
    for key, (kind, handler) in event_handlers.items():
        if key in event_type:
            entity_id = data.get(f"{key}_id")
            if action == "register":
                entity = await handler(entity_id)
                await ocean.register_raw(kind, [entity])
                logger.info(f"Registered {kind} for event {event_type}")
            else:
                try:
                    await ocean.unregister_raw(kind, [{"id": entity_id}])
                    logger.info(f"Unregistered {kind} for event {event_type}")
                except Exception as e:
                    logger.error(f"Exception {e} occurred while attempting to unregister raw")
            break
    logger.info("Webhook event processed")
    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean ClickUp integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return
    await setup_application()
