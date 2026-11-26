from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun

from azure_integration.foundry.clients.http.foundry_client import create_foundry_client


class AbstractFoundryExecutor(AbstractExecutor):
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self.client = create_foundry_client()

    async def is_close_to_rate_limit(self, run: IntegrationRun) -> bool:
        return self.client.rate_limiter.is_close_to_rate_limit()

    async def get_remaining_seconds_until_rate_limit(
        self, run: IntegrationRun
    ) -> float:
        return self.client.rate_limiter.seconds_until_rate_limit_reset()

    async def _catalog(
        self,
        *,
        register: bool,
        kind: str,
        raw: dict[str, Any],
        run: IntegrationRun,
    ) -> None:
        """Best-effort catalog sync; never fail the action on catalog errors."""
        try:
            if register:
                await ocean.register_raw(kind, [raw])
            else:
                await ocean.unregister_raw(kind, [raw])
        except Exception as error:
            verb = "upsert" if register else "delete"
            message = f"Failed to {verb} {kind} in the catalog (continuing): {error}"
            logger.warning(message)
            await ocean.port_client.post_run_log(
                run, message, level="WARNING", should_raise=False
            )

    async def register_entity(
        self, kind: str, raw: dict[str, Any], run: IntegrationRun
    ) -> None:
        await self._catalog(register=True, kind=kind, raw=raw, run=run)

    async def unregister_entity(
        self, kind: str, raw: dict[str, Any], run: IntegrationRun
    ) -> None:
        await self._catalog(register=False, kind=kind, raw=raw, run=run)
