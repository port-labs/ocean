from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from actions.registry import register_action_executors
from exporter_factory import (
    create_agents_exporter,
    create_environments_exporter,
    create_memory_stores_exporter,
    create_sessions_exporter,
    create_skills_exporter,
    create_vaults_exporter,
)
from integration import ObjectKind
from webhook_processors.registry import register_live_events_webhooks


@ocean.on_resync(ObjectKind.AGENT)
async def on_resync_agents(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_agents_exporter()
    async for page in exporter.get_paginated_resources():
        if page:
            yield page


@ocean.on_resync(ObjectKind.ENVIRONMENT)
async def on_resync_environments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_environments_exporter()
    async for page in exporter.get_paginated_resources():
        if page:
            yield page


@ocean.on_resync(ObjectKind.SESSION)
async def on_resync_sessions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_sessions_exporter()
    async for page in exporter.get_paginated_resources():
        if page:
            yield page


@ocean.on_resync(ObjectKind.VAULT)
async def on_resync_vaults(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_vaults_exporter()
    async for page in exporter.get_paginated_resources():
        if page:
            yield page


@ocean.on_resync(ObjectKind.MEMORY_STORE)
async def on_resync_memory_stores(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_memory_stores_exporter()
    async for page in exporter.get_paginated_resources():
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
    # Anthropic webhooks are configured in the Claude Console (there is no
    # create-subscription API), so there is nothing to register on the Anthropic
    # side here - the integration only verifies incoming webhook signatures.
    logger.info("Starting claude-managed-agents integration")


# Register live event webhook processors (catalog updates for sessions and vaults)
register_live_events_webhooks()

# Register action executors (create_agent, trigger_agent). The trigger_agent
# webhook processor is auto-registered by the execution manager.
register_action_executors()
