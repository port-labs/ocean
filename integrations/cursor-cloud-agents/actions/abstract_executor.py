from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun

from clients.client_factory import create_cursor_agents_client
from core.catalog import upsert_raw_entity


class AbstractCursorExecutor(AbstractExecutor):
    """Base executor for Cursor Cloud Agents actions."""

    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self.client = create_cursor_agents_client()

    async def is_close_to_rate_limit(self) -> bool:
        """The Cursor Cloud Agents API doesn't expose rate-limit state via
        response headers (see `CursorAgentsClient`), so there's nothing to
        check proactively here - `429`/`5xx` backoff is handled reactively by
        Ocean's retryable HTTP transport on each request."""
        return False

    async def get_remaining_seconds_until_rate_limit(self) -> float:
        return 0.0

    async def register_entity(
        self, kind: str, raw: dict[str, Any], run: IntegrationRun
    ) -> None:
        try:
            await upsert_raw_entity(
                kind, raw, console_host=self.client.get_console_host()
            )
        except Exception as error:
            message = f"Failed to upsert {kind} into the catalog (continuing): {error}"
            logger.warning(message)
            try:
                await ocean.port_client.post_run_log(run, message, level="WARNING")
            except Exception as log_error:
                logger.warning(
                    f"Failed to post run log for catalog upsert failure: {log_error}"
                )
