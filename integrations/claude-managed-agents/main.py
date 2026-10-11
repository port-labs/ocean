from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from actions.registry import register_action_executors
from clients.client_factory import create_anthropic_client
from exporter_factory import (
    create_agents_exporter,
    create_environments_exporter,
    create_memory_stores_exporter,
    create_sessions_exporter,
    create_skills_exporter,
    create_vaults_exporter,
)
from integration import (
    AgentResourceConfig,
    EnvironmentResourceConfig,
    MemoryStoreResourceConfig,
    ObjectKind,
    SessionResourceConfig,
    VaultResourceConfig,
)
from webhook_processors.registry import register_live_events_webhooks


@ocean.on_resync(ObjectKind.AGENT)
async def on_resync_agents(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(AgentResourceConfig, event.resource_config).selector
    exporter = create_agents_exporter()
    async for page in exporter.get_paginated_resources(
        include_archived=selector.include_archived
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.ENVIRONMENT)
async def on_resync_environments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(EnvironmentResourceConfig, event.resource_config).selector
    exporter = create_environments_exporter()
    async for page in exporter.get_paginated_resources(
        include_archived=selector.include_archived
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.SESSION)
async def on_resync_sessions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(SessionResourceConfig, event.resource_config).selector
    exporter = create_sessions_exporter()
    async for page in exporter.get_paginated_resources(
        include_archived=selector.include_archived
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.VAULT)
async def on_resync_vaults(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(VaultResourceConfig, event.resource_config).selector
    exporter = create_vaults_exporter()
    async for page in exporter.get_paginated_resources(
        include_archived=selector.include_archived
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.MEMORY_STORE)
async def on_resync_memory_stores(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(MemoryStoreResourceConfig, event.resource_config).selector
    exporter = create_memory_stores_exporter()
    async for page in exporter.get_paginated_resources(
        include_archived=selector.include_archived
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.SKILL)
async def on_resync_skills(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_skills_exporter()
    async for page in exporter.get_paginated_resources():
        if page:
            yield page


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting claude-managed-agents integration")

    if not ocean.app.config.event_listener.should_process_webhooks:
        logger.info("Skipping Claude webhook create (event listener)")
        return
    if not ocean.app.base_url:
        logger.warning("Skipping Claude webhook create (no OCEAN__BASE_URL)")
        return
    await create_anthropic_client().create_webhooks_if_not_exists(ocean.app.base_url)


register_live_events_webhooks()
register_action_executors()
