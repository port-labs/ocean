from enum import StrEnum
from typing import Any, Dict
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from client import ClickupClient

EVENT_ACTIONS = {
    "listCreated": "register",
    "listUpdated": "register",
    "listDeleted": "unregister",
    "taskCreated": "register",
    "taskUpdated": "register",
    "taskDeleted": "unregister",
    "spaceCreated": "register",
    "spaceUpdated": "register",
    "spaceDeleted": "unregister",
}


class ObjectKind(StrEnum):
    TEAM = "team"
    SPACE = "space"
    PROJECT = "project"
    ISSUE = "issue"


async def init_client() -> ClickupClient:
    client = ClickupClient(
        ocean.integration_config["clickup_base_url"],
        ocean.integration_config["clickup_personal_token"],
        ocean.integration_config["include_archived_projects"],
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
    async for teams in clickup_client.get_clickup_teams():
        for team in teams:
            webhooks = await clickup_client.get_clickup_webhooks(team["id"])
            webhook_exists = any(
                config["endpoint"] == f"{app_host}/integration/webhook"
                for config in webhooks
            )
            if webhook_exists:
                logger.info(f"Webhook already exists for team {team['id']}")
            else:
                logger.info(f"Creating webhook for team {team['id']}")


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    clickup_client = await init_client()
    async for teams in clickup_client.get_clickup_teams():
        logger.info(f"Received team of length {len(teams)}")
        yield teams


@ocean.on_resync(ObjectKind.SPACE)
async def on_resync_spaces(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    clickup_client = await init_client()
    async for spaces in clickup_client.get_all_spaces():
        logger.info(f"Received space batch with {len(spaces)} spaces")
        yield spaces


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    clickup_client = await init_client()
    async for folderless_projects in clickup_client.get_folderless_projects():
        logger.info(
            f"Received folderless project batch with {len(folderless_projects)} projects"
        )
        yield folderless_projects
    async for projects in clickup_client.get_folder_projects():
        logger.info(
            f"Received a batch of project in folders with {len(projects)} projects"
        )
        yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    clickup_client = await init_client()
    async for issues in clickup_client.get_paginated_issues():
        logger.info(f"Received issue batch with {len(issues)} issues")
        yield issues


async def handle_register(
    clickup_client: Any, entity_id: str, kind: ObjectKind, event_type: str
) -> None:
    if kind == ObjectKind.ISSUE:
        entity = await clickup_client.get_single_issue(entity_id)
    elif kind == ObjectKind.PROJECT:
        entity = await clickup_client.get_single_project(entity_id)
    else:
        entity = await clickup_client.get_single_space(entity_id)

    if entity:
        await ocean.register_raw(kind, [entity])
        logger.info(f"Registered {kind} for event {event_type}")
    else:
        logger.error(f"Handler returned None for entity_id {entity_id}")


async def handle_unregister(entity_id: str, kind: ObjectKind, event_type: str) -> None:
    try:
        await ocean.unregister_raw(kind, [{"id": entity_id}])
        logger.info(f"Unregistered {kind} for event {event_type}")
    except Exception as e:
        logger.error(f"Exception {e} occurred while attempting to unregister raw")


@ocean.router.post("/webhook")
async def handle_webhook_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle the webhook request from ClickUp.
    Events are mapped to the appropriate actions in event_handlers.
    """
    clickup_client = await init_client()
    logger.info(f"Received webhook event of type: {data.get('event')}")

    event_handlers = {
        "task": ObjectKind.ISSUE,
        "list": ObjectKind.PROJECT,
        "space": ObjectKind.SPACE,
    }

    event_type = data["event"]
    action = "unregister" if "Deleted" in event_type else "register"

    for key, kind in event_handlers.items():
        if key in event_type:
            entity_id = data.get(f"{key}_id")
            if not entity_id:
                logger.error(f"No {key}_id found in data for event {event_type}")
                continue
            if action == "register":
                await handle_register(clickup_client, entity_id, kind, event_type)
            else:
                await handle_unregister(entity_id, kind, event_type)
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
