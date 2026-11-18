from __future__ import annotations

from loguru import logger
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
    find_in_progress_run_for_response,
    is_response_completion_claimed,
)
from azure_integration.foundry.helpers.webhook_scope import (
    response_id_from_webhook_payload,
)

WEBHOOK_PATH = "/webhook"

_RESPONSE_TERMINAL_EVENTS = {
    "response.completed",
    "response.failed",
    "response.cancelled",
    "response.incomplete",
}

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
        return isinstance(event_type, str) and event_type in _RESPONSE_TERMINAL_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return []

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig | None
    ) -> WebhookEventRawResults:
        event_type = str(payload.get("type") or "")
        response_id = response_id_from_webhook_payload(payload)
        if not response_id:
            logger.warning(
                f"Ignoring Foundry webhook without response id ({event_type})"
            )
            return _EMPTY
        if is_response_completion_claimed(response_id):
            logger.debug(
                f"Ignoring Foundry webhook {event_type} for {response_id}; "
                "run already completed"
            )
            return _EMPTY

        run = await find_in_progress_run_for_response(response_id)
        if run is None or not run.execution_properties.get(
            "reportInvocationStatus", True
        ):
            return _EMPTY

        await complete_invoke_run_from_webhook(
            run,
            event_type=event_type,
            response_id=response_id,
        )
        return _EMPTY
