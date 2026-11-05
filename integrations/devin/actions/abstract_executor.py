from typing import Any

from loguru import logger
from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun

from clients.client_factory import create_devin_client
from core.sessions import DevinSessions


class AbstractDevinExecutor(AbstractExecutor):
    """Base executor for Devin actions."""

    # `AbstractExecutor` only declares this as a type annotation, so without this
    # default `execution_manager.register_executor` raises `AttributeError`.
    # Devin has no webhooks: tracked runs are completed by the `SessionTracker`.
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self.sessions = DevinSessions(create_devin_client())

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        """Devin exposes no rate-limit state; 429s are retried by the transport."""
        return False

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return 0.0

    async def register_entity(
        self, kind: str, raw: dict[str, Any], run: IntegrationRun
    ) -> None:
        """Best-effort upsert of a raw object into the catalog.

        `register_raw` reads `event.event_type`, and Port's API rejects the
        execution manager's own `ACTION_RUN` event type for entity upserts, so
        we open a nested `HTTP_REQUEST` context here.

        The port app config must be fetched *before* opening that nested
        context: entering a nested `event_context` eagerly inherits
        `port_app_config` from the active context, raising if it was never
        populated, which is always true for the action-run context the
        execution manager provides.

        Catalog reflection must never fail the action run, so failures are
        logged and reported as a run log, never raised.
        """
        try:
            await ocean.integration.port_app_config_handler.get_port_app_config(
                use_cache=False
            )
            async with event_context(EventType.HTTP_REQUEST, trigger_type="machine"):
                await ocean.register_raw(kind, [raw])
        except Exception as error:
            message = f"Failed to upsert {kind} into the catalog (continuing): {error}"
            logger.warning(message)
            try:
                await ocean.port_client.post_run_log(run, message, level="WARNING")
            except Exception as log_error:
                logger.warning(
                    f"Failed to post run log for catalog upsert failure: {log_error}"
                )
