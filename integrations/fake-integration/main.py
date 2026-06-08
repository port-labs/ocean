import asyncio
from typing import cast
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from loguru import logger

from fake_org_data.fake_client import (
    get_fake_json_file,
    get_fake_persons,
    get_departments,
    get_fake_codeowners_file,
    get_fake_yaml_file,
    get_fake_repositories,
    get_in_batches,
    invoke_fake_webhook_event,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from fake_org_data.fake_router import initialize_fake_routes
from webhook_processors import register_live_events_webhooks
from fake_org_data.types import FakeObjectKind, FakeSelector


@ocean.on_resync(FakeObjectKind.FAKE_DEPARTMENT)
async def resync_department(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if event.resource_config is None:
        yield []

    resource_config = cast(ResourceConfig, event.resource_config)
    selector = cast(FakeSelector, resource_config.selector)

    async for department_batch in get_in_batches(selector, get_departments):
        logger.info(f"Got a batch of {len(department_batch)} departments")
        yield department_batch


@ocean.on_resync(FakeObjectKind.FAKE_PERSON)
async def resync_persons(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if event.resource_config is None:
        yield []

    resource_config = cast(ResourceConfig, event.resource_config)
    selector = cast(FakeSelector, resource_config.selector)
    async for persons_batch in get_in_batches(selector, get_fake_persons):
        logger.info(f"Got a batch of {len(persons_batch)} persons")
        yield persons_batch


@ocean.on_resync(FakeObjectKind.FAKE_FILE)
async def resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if event.resource_config is None:
        yield []

    resource_config = cast(ResourceConfig, event.resource_config)
    selector = cast(FakeSelector, resource_config.selector)
    # Get file_path - it should be available on FakeSelector
    file_path = getattr(selector, "file_path", None) or "readme.md"

    if file_path.endswith(".txt"):
        async for codeowners_batch in get_in_batches(
            selector, get_fake_codeowners_file
        ):
            logger.info(f"Got a batch of {len(codeowners_batch)} codeowners files")
            yield codeowners_batch
    elif file_path.endswith(".yaml") or file_path.endswith(".yml"):
        async for yaml_batch in get_in_batches(selector, get_fake_yaml_file):
            logger.info(f"Got a batch of {len(yaml_batch)} yaml files")
            yield yaml_batch
    elif file_path.endswith(".json"):
        async for json_batch in get_in_batches(selector, get_fake_json_file):
            logger.info(f"Got a batch of {len(json_batch)} json files")
            yield json_batch
    else:
        logger.warning(
            f"Unknown file extension for file_path: {file_path}, defaulting to JSON"
        )
        async for json_batch in get_in_batches(selector, get_fake_json_file):
            logger.info(f"Got a batch of {len(json_batch)} json files")
            yield json_batch


@ocean.on_resync(FakeObjectKind.FAKE_REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if event.resource_config is None:
        yield []

    resource_config = cast(ResourceConfig, event.resource_config)
    selector = cast(FakeSelector, resource_config.selector)
    async for repositories_batch in get_in_batches(selector, get_fake_repositories):
        logger.info(f"Got a batch of {len(repositories_batch)} repositories")
        yield repositories_batch


@ocean.on_resync(FakeObjectKind.INVOKE_FAKE_WEBHOOK_EVENT)
async def invoke_webhook_event(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info("Invoked webhok event")
    if event.resource_config is None:
        yield []

    resource_config = cast(ResourceConfig, event.resource_config)
    selector = cast(FakeSelector, resource_config.selector)
    async for webhook_event_batch in get_in_batches(
        selector, invoke_fake_webhook_event
    ):
        logger.info(f"Got a batch of {len(webhook_event_batch)} webhook events")

        yield []


initialize_fake_routes()

# Register webhook processors for live events
register_live_events_webhooks()

asyncio.create_task(ocean.app._register_addons())


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting fake integration!")
