from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from actions.registry import register_action_executors
from exporter_factory import create_agents_exporter, create_runs_exporter
from integration import AgentResourceConfig, ObjectKind, RunResourceConfig


@ocean.on_resync(ObjectKind.AGENT)
async def on_resync_agents(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(AgentResourceConfig, event.resource_config).selector
    exporter = create_agents_exporter()
    async for page in exporter.get_paginated_resources(
        include_archived=selector.include_archived
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.RUN)
async def on_resync_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(RunResourceConfig, event.resource_config).selector
    exporter = create_runs_exporter()
    async for page in exporter.get_paginated_resources(
        include_archived=selector.include_archived
    ):
        if page:
            yield page


@ocean.on_start()
async def on_start() -> None:
    # v0 webhooks are configured per-agent at launch time (there is no
    # account-wide webhook subscription API), so there is nothing to register
    # on the Cursor side here - the integration only verifies incoming webhook
    # signatures.
    logger.info("Starting cursor-cloud-agents integration")


register_action_executors()
