from __future__ import annotations

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
    WebhookProcessorType,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from azure_integration.foundry.helpers.invoke_completion import (
    complete_invoke_run_from_webhook,
)
from azure_integration.foundry.models.responses import TERMINAL_EVENTS

WEBHOOK_PATH = "/webhook"

_EMPTY = WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])


class ConversationWebhookProcessor(AbstractWebhookProcessor):
    """Completes invoke runs correlated by Foundry ``response.*`` webhooks."""

    @classmethod
    def get_processor_type(cls) -> WebhookProcessorType:
        return WebhookProcessorType.ACTION

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        # Foundry returns a platform signing_secret per account webhook (no custom
        # secret). Multi-account → multi-secret with no clean user config. Trust is
        # correlation: handlers only act on response ids bound to in-progress runs.
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return isinstance(payload.get("type"), str) and bool(payload.get("id"))

    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("type")
        return isinstance(event_type, str) and event_type in TERMINAL_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return []

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig | None
    ) -> WebhookEventRawResults:
        event_type = str(payload.get("type") or "")
        data = payload.get("data")
        raw_id = data.get("id") if isinstance(data, dict) else None
        response_id = str(raw_id) if raw_id else ""
        if not response_id:
            logger.warning(
                f"Ignoring Foundry webhook without response id ({event_type})"
            )
            return _EMPTY

        run = await ocean.port_client.find_run_by_external_id(response_id)
        if run is None or not run.execution_properties.get(
            "reportInvocationStatus", False
        ):
            return _EMPTY

        await complete_invoke_run_from_webhook(
            run,
            event_type=event_type,
            response_id=response_id,
        )
        return _EMPTY
