from typing import Any

from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun

from clients.client_factory import create_devin_client
from actions.utils import upsert_raw_best_effort
from core.sessions import DevinSessions


class AbstractDevinExecutor(AbstractExecutor):
    # `AbstractExecutor` only declares this as a type annotation, so without this
    # default `execution_manager.register_executor` raises `AttributeError`.
    # Devin has no webhooks: tracked runs are completed by the `SessionTracker`.
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self.sessions = DevinSessions(create_devin_client())

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return False

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return 0.0

    async def register_entity(
        self, kind: str, raw: dict[str, Any], run: IntegrationRun
    ) -> None:
        await upsert_raw_best_effort(kind, raw, run)
