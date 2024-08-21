from enum import StrEnum
from typing import Any, Dict
from loguru import logger
from port_ocean.context.ocean import ocean
from client import ClickupClient


class ObjectKind(StrEnum):
    TEAM = "team"
    SPACE = "space"
    PROJECT = "project"
    TASK = "task"


async def init_client() -> ClickupClient:
    client = ClickupClient(
        ocean.integration_config["clickup_base_url"],
        ocean.integration_config["clickup_personal_token"],
        ocean.integration_config["include_archived_projects"],
        ocean.integration_config.get("workspace_ids"),
    )
    return client


WEBHOOK_TEAM_MAP = {}


async def handle_webhook_creation(app_host: str) -> None:
    clickup_client = await init_client()
    async for teams in clickup_client.get_clickup_teams():
        for team in teams:
            webhooks = await clickup_client.get_clickup_webhooks(team["id"])
            webhook_found = False
            for webhook in webhooks:
                if webhook["endpoint"] == f"{app_host}/integration/webhook":
                    logger.info(f"Webhook already exists for team {team['id']}")
                    WEBHOOK_TEAM_MAP[webhook["id"]] = team["id"]
                    webhook_found = True
                    break
            if not webhook_found:
                logger.info(f"Creating webhook for team {team['id']}")
                webhook = await clickup_client.create_clickup_webhook(
                    team["id"], app_host
                )
                WEBHOOK_TEAM_MAP[webhook["id"]] = team["id"]


async def handle_register(
    clickup_client: Any,
    entity_id: str,
    kind: ObjectKind,
    event_type: str,
    webhook_id: str,
) -> None:
    team_id = WEBHOOK_TEAM_MAP.get(webhook_id)
    if kind == ObjectKind.TASK:
        entity = await clickup_client.get_single_task(entity_id)
    elif kind == ObjectKind.PROJECT:
        entity = await clickup_client.get_single_project(entity_id, team_id)
    else:
        entity = await clickup_client.get_single_space(entity_id, team_id)

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


async def process_webhook_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle the webhook request from ClickUp.
    Events are mapped to the appropriate actions in event_handlers.
    """
    clickup_client = await init_client()
    event_handlers = {
        "task": ObjectKind.TASK,
        "list": ObjectKind.PROJECT,
        "space": ObjectKind.SPACE,
    }
    event_type = data["event"]
    webhook_id = data["webhook_id"]

    for key, kind in event_handlers.items():
        if key in event_type:
            entity_id = data.get(f"{key}_id")
            if not entity_id:
                logger.error(f"No {key}_id found in data for event {event_type}")
                continue
            if "Deleted" in event_type:
                await handle_unregister(entity_id, kind, event_type)
            else:
                await handle_register(
                    clickup_client, entity_id, kind, event_type, webhook_id
                )
            break

    logger.info("Webhook event processed")
    return {"ok": True}
