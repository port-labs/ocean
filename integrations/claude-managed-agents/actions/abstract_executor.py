from typing import Any, Optional, Type

from loguru import logger
from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)

from clients.client_factory import create_anthropic_client

# Below this fraction of remaining create-endpoint requests, new actions back
# off until the create rate limit window resets. A percentage (rather than an
# absolute count) keeps this correct regardless of the account's RPM tier.
CREATE_RATE_LIMIT_HEADROOM_RATIO = 0.1


class AbstractAnthropicExecutor(AbstractExecutor):
    """Base executor for Claude Managed Agents actions."""

    WEBHOOK_PROCESSOR_CLASS: Optional[Type[AbstractWebhookProcessor]] = None
    WEBHOOK_PATH: str = ""

    def __init__(self) -> None:
        self.client = create_anthropic_client()

    async def is_close_to_rate_limit(self) -> bool:
        """Throttles on the create-endpoints RPM limit only (see
        `AnthropicClient.get_create_rate_limit_status`); read-endpoint calls
        are not gated. A stale cache past its reset is treated as replenished,
        since nothing refreshes it while this backoff loop is running.
        """
        info = self.client.get_create_rate_limit_status()
        if info is None or info.limit == 0 or info.seconds_until_reset <= 0:
            return False
        return info.remaining / info.limit < CREATE_RATE_LIMIT_HEADROOM_RATIO

    async def get_remaining_seconds_until_rate_limit(self) -> float:
        info = self.client.get_create_rate_limit_status()
        return info.seconds_until_reset if info else 0.0

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
