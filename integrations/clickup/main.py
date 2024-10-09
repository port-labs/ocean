from typing import Any, Dict
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from webhook import (
    handle_webhook_creation,
    process_webhook_request,
    init_client,
    ObjectKind,
)


async def setup_application() -> None:
    app_host = ocean.integration_config.get("app_host")
    if not app_host:
        logger.warning(
            "App host was not provided, skipping webhook creation. "
            "Without setting up the webhook, you will have to manually initiate resync to get updates from ClickUp."
        )
        return
    await handle_webhook_creation(app_host)


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    clickup_client = await init_client()
    async for teams in clickup_client.get_clickup_teams():
        logger.info(f"Received batch of {len(teams)} teams")
        yield teams


@ocean.on_resync(ObjectKind.SPACE)
async def on_resync_spaces(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    clickup_client = await init_client()
    async for spaces in clickup_client.get_all_spaces():
        logger.info(f"Received batch of {len(spaces)} spaces")
        yield spaces


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    clickup_client = await init_client()
    async for projects in clickup_client.get_all_projects():
        logger.info(f"Received batch of  {len(projects)} projects")
        yield projects


@ocean.on_resync(ObjectKind.TASK)
async def on_resync_tasks(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    clickup_client = await init_client()
    async for tasks in clickup_client.get_paginated_tasks():
        logger.info(f"Received batch of {len(tasks)} tasks")
        yield tasks


@ocean.router.post("/webhook")
async def handle_webhook_request(data: Dict[str, Any]) -> Dict[str, Any]:
    logger.info(f"Received webhook event of type: {data}")
    response = await process_webhook_request(data)
    return response


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean ClickUp integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return
    await setup_application()
