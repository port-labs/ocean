from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.signal import signal_handler

from actions.registry import register_action_executors
from core.tracking.session_tracker import create_session_tracker
from exporter_factory import (
    create_knowledge_notes_exporter,
    create_playbooks_exporter,
    create_secrets_exporter,
    create_sessions_exporter,
)
from integration import ObjectKind, PlaybookResourceConfig, SessionResourceConfig


@ocean.on_resync(ObjectKind.SESSION)
async def on_resync_sessions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(SessionResourceConfig, event.resource_config).selector
    exporter = create_sessions_exporter()
    async for page in exporter.get_paginated_resources(
        include_archived=selector.include_archived,
        created_after_days=selector.created_after_days,
        origins=list(selector.origins) if selector.origins else None,
        only_managed_by_port=selector.only_managed_by_port,
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.PLAYBOOK)
async def on_resync_playbooks(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(PlaybookResourceConfig, event.resource_config).selector
    exporter = create_playbooks_exporter()
    async for page in exporter.get_paginated_resources(
        include_enterprise=selector.include_enterprise
    ):
        if page:
            yield page


@ocean.on_resync(ObjectKind.KNOWLEDGE_NOTE)
async def on_resync_knowledge_notes(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_knowledge_notes_exporter()
    async for page in exporter.get_paginated_resources():
        if page:
            yield page


@ocean.on_resync(ObjectKind.SECRET)
async def on_resync_secrets(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = create_secrets_exporter()
    async for page in exporter.get_paginated_resources():
        if page:
            yield page


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting devin integration")
    config = ocean.app.config
    if not (
        config.actions_processor.enabled and config.event_listener.should_run_actions
    ):
        logger.info(
            "Not starting the Devin session tracker because this instance does "
            "not process actions (set OCEAN__ACTIONS_PROCESSOR__ENABLED=true)"
        )
        return

    tracker = create_session_tracker()
    signal_handler.register(tracker.stop)
    await tracker.start()


register_action_executors()
