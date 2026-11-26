from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from integration import PromptResourceConfig, SessionResourceConfig
from langfuse.clients.client_factory import create_langfuse_client
from langfuse.core.exporters import (
    DatasetExporter,
    ModelExporter,
    ProjectExporter,
    PromptExporter,
    SessionExporter,
)
from langfuse.core.exporters.prompt_exporter import PROMPT_INCREMENTAL
from langfuse.core.exporters.session_exporter import SESSION_INCREMENTAL
from langfuse.core.options import ListPromptOptions, ListSessionOptions
from langfuse.helpers.utils import ObjectKind
from langfuse.webhook.registry import register_live_events_webhooks


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = ProjectExporter(create_langfuse_client())
    async for batch in exporter.get_paginated_resources():
        yield batch


@ocean.on_incremental_resync(ObjectKind.PROMPT)
@ocean.on_resync(ObjectKind.PROMPT)
async def on_resync_prompts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(PromptResourceConfig, event.resource_config).selector
    cursor = active_incremental_cursor()
    params = PROMPT_INCREMENTAL.merge_params({}, cursor)

    exporter = PromptExporter(create_langfuse_client())
    async for batch in exporter.get_paginated_resources(
        ListPromptOptions(
            from_updated_at=params.get("fromUpdatedAt"),
            label=selector.label,
            tag=selector.tag,
        )
    ):
        yield batch


@ocean.on_resync(ObjectKind.DATASET)
async def on_resync_datasets(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = DatasetExporter(create_langfuse_client())
    async for batch in exporter.get_paginated_resources():
        yield batch


@ocean.on_resync(ObjectKind.MODEL)
async def on_resync_models(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = ModelExporter(create_langfuse_client())
    async for batch in exporter.get_paginated_resources():
        yield batch


@ocean.on_incremental_resync(ObjectKind.SESSION)
@ocean.on_resync(ObjectKind.SESSION)
async def on_resync_sessions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(SessionResourceConfig, event.resource_config).selector
    cursor = active_incremental_cursor()
    params = SESSION_INCREMENTAL.merge_params({}, cursor)

    exporter = SessionExporter(create_langfuse_client())
    async for batch in exporter.get_paginated_resources(
        ListSessionOptions(
            from_start_time=params.get("fromStartTime"),
            lookback_days=selector.lookback_days,
        )
    ):
        yield batch


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Langfuse integration (project-scoped)")
    register_live_events_webhooks()
