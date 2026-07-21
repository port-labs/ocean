from typing import Any

from loguru import logger
from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.abstract_executor import AbstractExecutor
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.models import IntegrationRun

from clients.anthropic_client import RateLimitInfo
from clients.client_factory import create_anthropic_client

# Below this fraction of remaining requests in a pool, new actions back off
# until that pool's rate limit window resets. A percentage (rather than an
# absolute count) keeps this correct regardless of the account's RPM tier.
RATE_LIMIT_HEADROOM_RATIO = 0.1


class AbstractAnthropicExecutor(AbstractExecutor):
    """Base executor for Claude Managed Agents actions."""

    # `AbstractExecutor` only declares this as a type annotation, not an actual
    # class attribute, so subclasses without a webhook (e.g. `CreateAgentExecutor`)
    # would otherwise raise `AttributeError` when `execution_manager.register_executor`
    # reads it. Executors that do have one (e.g. `TriggerAgentExecutor`) override it.
    WEBHOOK_PROCESSOR_CLASS: type[AbstractWebhookProcessor] | None = None

    def __init__(self) -> None:
        self.client = create_anthropic_client()

    @staticmethod
    def _is_pool_close_to_exhausted(info: RateLimitInfo | None) -> bool:
        """A stale cache past its reset is treated as replenished, since
        nothing refreshes it while this backoff loop is running."""
        if info is None or info.limit == 0 or info.seconds_until_reset <= 0:
            return False
        return info.remaining / info.limit < RATE_LIMIT_HEADROOM_RATIO

    async def is_close_to_rate_limit(self) -> bool:
        """Defers starting a new action run once either Managed Agents RPM
        pool (create or read; see `AnthropicClient.get_create_rate_limit_status`/
        `get_read_rate_limit_status`) is close to exhausted.

        Both pools matter here even though only create/send calls mutate
        state: continuing a session (`TriggerAgentExecutor._ensure_session_continuable`)
        makes only read calls before ever reaching `send_user_message`, so
        gating on the create pool alone would let those runs start and then
        stall mid-flight in the client's own proactive-sleep hook instead of
        deferring the whole run up front.
        """
        return self._is_pool_close_to_exhausted(
            self.client.get_create_rate_limit_status()
        ) or self._is_pool_close_to_exhausted(self.client.get_read_rate_limit_status())

    async def get_remaining_seconds_until_rate_limit(self) -> float:
        """Waits out whichever pool(s) are currently close to exhausted, so
        the execution manager doesn't retry before all of them have
        replenished."""
        infos = (
            self.client.get_create_rate_limit_status(),
            self.client.get_read_rate_limit_status(),
        )
        waits = [
            info.seconds_until_reset
            for info in infos
            if info is not None and self._is_pool_close_to_exhausted(info)
        ]
        return max(waits, default=0.0)

    async def register_entity(
        self, kind: str, raw: dict[str, Any], run: IntegrationRun
    ) -> None:
        """Best-effort upsert of a raw object into the catalog.

        `register_raw` reads `event.event_type`, and Port's API rejects the
        execution manager's own `ACTION_RUN` event type for entity upserts, so
        we open a nested `HTTP_REQUEST` context here.

        The port app config must be fetched *before* opening that nested
        context, not inside it: entering a nested `event_context` eagerly
        inherits `port_app_config` from whichever context is already active,
        raising immediately if that parent's config was never populated -
        which is always true for the action-run context the execution manager
        provides. Fetching it first sets it on the still-active outer context,
        so the nested context inherits it successfully instead of raising.

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
