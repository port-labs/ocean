from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.signal import signal_handler

from actions.archive_session_executor import ArchiveSessionExecutor
from actions.create_session_executor import CreateSessionExecutor
from actions.send_message_executor import SendMessageExecutor
from actions.terminate_session_executor import TerminateSessionExecutor
from clients.client_factory import create_devin_client
from core.exporters.knowledge_notes_exporter import KnowledgeNotesExporter
from core.exporters.options import PlaybooksExportOptions, SessionsExportOptions
from core.exporters.playbooks_exporter import PlaybooksExporter
from core.exporters.secrets_exporter import SecretsExporter
from core.exporters.sessions_exporter import SessionsExporter
from core.tracking.session_tracker import create_session_tracker
from integration import ObjectKind, PlaybookResourceConfig, SessionResourceConfig


@ocean.on_resync(ObjectKind.SESSION)
async def on_resync_sessions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(SessionResourceConfig, event.resource_config).selector
    exporter = SessionsExporter(create_devin_client())
    options: SessionsExportOptions = {
        "include_archived": selector.include_archived,
        "created_after_days": selector.created_after_days,
        "origins": list(selector.origins) if selector.origins else None,
        "only_managed_by_port": selector.only_managed_by_port,
    }
    async for page in exporter.get_paginated_resources(options):
        yield page


@ocean.on_resync(ObjectKind.PLAYBOOK)
async def on_resync_playbooks(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    selector = cast(PlaybookResourceConfig, event.resource_config).selector
    exporter = PlaybooksExporter(create_devin_client())
    options = PlaybooksExportOptions(
        include_enterprise=selector.include_enterprise,
    )
    async for page in exporter.get_paginated_resources(options):
        yield page


@ocean.on_resync(ObjectKind.KNOWLEDGE_NOTE)
async def on_resync_knowledge_notes(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = KnowledgeNotesExporter(create_devin_client())
    async for page in exporter.get_paginated_resources():
        yield page


@ocean.on_resync(ObjectKind.SECRET)
async def on_resync_secrets(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    exporter = SecretsExporter(create_devin_client())
    async for page in exporter.get_paginated_resources():
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


ocean.register_action_executor(CreateSessionExecutor())
ocean.register_action_executor(SendMessageExecutor())
ocean.register_action_executor(TerminateSessionExecutor())
ocean.register_action_executor(ArchiveSessionExecutor())
