from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.signal import signal_handler

from actions.registry import register_action_executors
from clients.client_factory import (
    create_foundry_client,
    create_webhook_client,
)
from helpers.arm_scope import ensure_arm_deployment_scope
from exporter_factory import (
    create_agent_versions_exporter,
    create_agents_exporter,
    create_responses_exporter,
    create_conversations_exporter,
    create_memory_stores_exporter,
    create_model_deployments_exporter,
    create_skills_exporter,
)
from integration import (
    AgentResourceConfig,
    ResponseResourceConfig,
    ConversationResourceConfig,
    ObjectKind,
)


@ocean.on_incremental_resync(ObjectKind.AGENT)
@ocean.on_resync(ObjectKind.AGENT)
async def on_resync_agents(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(AgentResourceConfig, event.resource_config).selector
    exporter = create_agents_exporter()
    async for page in exporter.get_paginated_resources(
        include_versions=selector.include_versions,
    ):
        if page:
            yield page


@ocean.on_incremental_resync(ObjectKind.AGENT_VERSION)
@ocean.on_resync(ObjectKind.AGENT_VERSION)
async def on_resync_agent_versions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_agent_versions_exporter()
    async for page in exporter.get_paginated_resources():
        if page:
            yield page


@ocean.on_incremental_resync(ObjectKind.MODEL_DEPLOYMENT)
@ocean.on_resync(ObjectKind.MODEL_DEPLOYMENT)
async def on_resync_model_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_model_deployments_exporter()
    async for page in exporter.get_paginated_resources():
        if page:
            yield page


@ocean.on_incremental_resync(ObjectKind.CONVERSATION)
@ocean.on_resync(ObjectKind.CONVERSATION)
async def on_resync_conversations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(ConversationResourceConfig, event.resource_config).selector
    exporter = create_conversations_exporter()
    async for page in exporter.get_paginated_resources(since_days=selector.since_days):
        if page:
            yield page


@ocean.on_incremental_resync(ObjectKind.RESPONSE)
@ocean.on_resync(ObjectKind.RESPONSE)
async def on_resync_responses(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(ResponseResourceConfig, event.resource_config).selector
    exporter = create_responses_exporter()
    async for page in exporter.get_paginated_resources(since_days=selector.since_days):
        if page:
            yield page


@ocean.on_incremental_resync(ObjectKind.SKILL)
@ocean.on_resync(ObjectKind.SKILL)
async def on_resync_skills(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_skills_exporter()
    async for page in exporter.get_paginated_resources():
        if page:
            yield page


@ocean.on_incremental_resync(ObjectKind.MEMORY_STORE)
@ocean.on_resync(ObjectKind.MEMORY_STORE)
async def on_resync_memory_stores(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_memory_stores_exporter()
    async for page in exporter.get_paginated_resources():
        if page:
            yield page


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting azure-ai-foundry integration")
    register_action_executors()
    signal_handler.register(_close_foundry_client)

    try:
        await ensure_arm_deployment_scope()
        logger.info("Resolved Azure ARM scope from Foundry project endpoint")
    except ValueError as error:
        logger.info(
            f"ARM scope not resolved at startup (optional until deploy/MCP): {error}"
        )

    if not ocean.app.config.event_listener.should_process_webhooks:
        logger.info(
            "Skipping Foundry webhook registration because webhooks are disabled"
        )
        return

    base_url = ocean.app.base_url
    if not base_url:
        logger.warning(
            "Skipping Foundry webhook registration: set OCEAN__BASE_URL so Foundry "
            "can deliver response.* events"
        )
        return

    await create_webhook_client().upsert_webhook(base_url)


async def _close_foundry_client() -> None:
    await create_foundry_client().close()
