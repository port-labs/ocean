from typing import Any

from loguru import logger
from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun

from factory_ai.clients.client_factory import ClientFactory
from factory_ai.clients.factory_client import FactoryClient


class AbstractFactoryExecutor(AbstractExecutor):
    """Base executor for Factory.ai actions.

    Owns the shared HTTP client and catalog reflection helpers so each action
    only implements ``execute``. Factory exposes no rate-limit headers, so
    backoff relies on Ocean's retrying transport.
    """

    # `AbstractExecutor` only declares this as a type annotation, not an actual
    # class attribute, so subclasses without a webhook rely on this default when
    # `register_executor` reads it. The annotated type keeps mypy happy when a
    # future subclass overrides it with a processor class.
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        # Resolved lazily so import-time registration does not require a fully
        # configured ocean context (actions may be disabled).
        self._client: FactoryClient | None = None

    @property
    def client(self) -> FactoryClient:
        if self._client is None:
            self._client = ClientFactory.get_client()
        return self._client

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return False

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return 0.0

    async def register_entity(
        self, kind: str, raw: dict[str, Any], run: IntegrationRun
    ) -> None:
        """Best-effort upsert of a raw object into the catalog.

        ``register_raw`` reads ``event.event_type``, and Port's API rejects the
        execution manager's ``ACTION_RUN`` event type for entity upserts, so we
        open a nested ``HTTP_REQUEST`` context. Catalog reflection must never
        fail the action run.
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
