from enum import StrEnum
from typing import Any, Callable, Coroutine

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_RESULT

from client import ClickupClient


class ObjectKind(StrEnum):
    TEAM = "team"
    PROJECT = "project"
    ISSUE = "issue"


def get_client() -> ClickupClient:
    return ClickupClient(ocean.integration_config["clickup_apikey"])


async def setup_application() -> None:
    app_host = ocean.integration_config.get("app_host")
    if not app_host:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Clickup"
        )
        return
    client = get_client()
    await client.create_webhook_events(app_host)


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> RAW_RESULT:
    client = get_client()
    return await client.get_teams()


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_client()
    async for projects in client.get_projects():
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = get_client()
    async for issues in client.get_paginated_issues():
        logger.info(f"Received issue batch with {len(issues)} issues")
        yield issues


async def handle_list_created_or_updated(data: dict[str, Any]) -> None:
    client = get_client()
    project = await client.get_single_project(data["list_id"])
    await ocean.register_raw(ObjectKind.PROJECT, [project])


async def handle_list_deleted(data: dict[str, Any]) -> None:
    await ocean.unregister_raw(ObjectKind.PROJECT, [{"id": data["list_id"]}])


async def handle_task_created_or_updated(data: dict[str, Any]) -> None:
    client = get_client()
    issue = await client.get_single_issue(data["task_id"])
    await ocean.register_raw(ObjectKind.ISSUE, [issue])


async def handle_task_deleted(data: dict[str, Any]) -> None:
    await ocean.unregister_raw(ObjectKind.ISSUE, [{"id": data["task_id"]}])


@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> dict[str, bool]:
    EVENT_HANDLERS: dict[str, Callable[[dict[str, Any]], Coroutine[Any, Any, None]]] = {
        "listCreated": handle_list_created_or_updated,
        "listUpdated": handle_list_created_or_updated,
        "listDeleted": handle_list_deleted,
        "taskCreated": handle_task_created_or_updated,
        "taskUpdated": handle_task_created_or_updated,
        "taskDeleted": handle_task_deleted,
    }
    event: str = data.get("event", "")
    logger.info(f"Received webhook event of type: {event}")
    handler = EVENT_HANDLERS.get(event, None)
    if not handler:
        logger.error(f"Unhandled event type: {event}")
        return {"ok": False}
    await handler(data)
    logger.info("Webhook event processed")
    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Clickup integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return
    await setup_application()
