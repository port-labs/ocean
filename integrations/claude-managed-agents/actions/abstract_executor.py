from typing import Any, Optional, Type

from loguru import logger
from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)

from clients.client_factory import create_anthropic_client


class AbstractAnthropicExecutor(AbstractExecutor):
    """Base executor for Claude Managed Agents actions."""

    WEBHOOK_PROCESSOR_CLASS: Optional[Type[AbstractWebhookProcessor]] = None
    WEBHOOK_PATH: str = ""

    def __init__(self) -> None:
        self.client = create_anthropic_client()

    async def is_close_to_rate_limit(self) -> bool:
        # The Anthropic SDK handles retries/backoff for rate limits internally.
        return False

    async def get_remaining_seconds_until_rate_limit(self) -> float:
        return 0.0

    async def register_entity(self, kind: str, raw: dict[str, Any]) -> None:
        """Best-effort upsert of a raw object into the catalog.

        `register_raw` requires an active event context with the port app config
        loaded (the action execution manager does not provide one), so we open a
        fresh context here. Catalog reflection must never fail the action run, so
        failures are logged and swallowed.
        """
        try:
            async with event_context(EventType.HTTP_REQUEST, trigger_type="machine"):
                await ocean.integration.port_app_config_handler.get_port_app_config(
                    use_cache=False
                )
                await ocean.register_raw(kind, [raw])
        except Exception as error:
            logger.warning(
                f"Failed to upsert {kind} into the catalog (continuing): {error}"
            )
