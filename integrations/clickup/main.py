from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clickup.helpers.utils import ObjectKind
from clickup.clients.client_factory import create_clickup_client
from clickup.core.exporters import (
    WorkspaceExporter,
    SpaceExporter,
    FolderExporter,
    ListExporter,
    TaskExporter,
)
from webhook_processors import (
    TaskWebhookProcessor,
    ListWebhookProcessor,
    FolderWebhookProcessor,
    SpaceWebhookProcessor,
)


@ocean.on_resync(ObjectKind.WORKSPACE)
async def resync_workspaces(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all workspaces from ClickUp."""
    logger.info("Starting workspaces resync")

    client = create_clickup_client()
    exporter = WorkspaceExporter(client)

    async for workspaces_batch in exporter.get_paginated_resources():
        logger.info(f"Yielding workspaces batch of size: {len(workspaces_batch)}")
        yield workspaces_batch


@ocean.on_resync(ObjectKind.SPACE)
async def resync_spaces(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all spaces from ClickUp."""
    logger.info("Starting spaces resync")

    client = create_clickup_client()
    exporter = SpaceExporter(client)

    async for spaces_batch in exporter.get_paginated_resources():
        logger.info(f"Yielding spaces batch of size: {len(spaces_batch)}")
        yield spaces_batch


@ocean.on_resync(ObjectKind.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all folders from ClickUp."""
    logger.info("Starting folders resync")

    client = create_clickup_client()
    exporter = FolderExporter(client)

    async for folders_batch in exporter.get_paginated_resources():
        logger.info(f"Yielding folders batch of size: {len(folders_batch)}")
        yield folders_batch


@ocean.on_resync(ObjectKind.LIST)
async def resync_lists(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all lists from ClickUp."""
    logger.info("Starting lists resync")

    client = create_clickup_client()
    exporter = ListExporter(client)

    async for lists_batch in exporter.get_paginated_resources():
        logger.info(f"Yielding lists batch of size: {len(lists_batch)}")
        yield lists_batch


@ocean.on_resync(ObjectKind.TASK)
async def resync_tasks(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all tasks from ClickUp."""
    logger.info("Starting tasks resync")

    client = create_clickup_client()
    exporter = TaskExporter(client)

    async for tasks_batch in exporter.get_paginated_resources():
        logger.info(f"Yielding tasks batch of size: {len(tasks_batch)}")
        yield tasks_batch


@ocean.on_start()
async def on_start() -> None:
    """Called once when the integration starts."""
    logger.info("Starting Port Ocean ClickUp integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook setup: event listener is ONCE")
        return


ocean.add_webhook_processor("/webhook", TaskWebhookProcessor)
ocean.add_webhook_processor("/webhook", ListWebhookProcessor)
ocean.add_webhook_processor("/webhook", FolderWebhookProcessor)
ocean.add_webhook_processor("/webhook", SpaceWebhookProcessor)
