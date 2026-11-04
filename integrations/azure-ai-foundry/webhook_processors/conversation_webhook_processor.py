from __future__ import annotations

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    WebhookProcessorType,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from helpers.invoke_completion import (
    complete_invoke_run_from_webhook,
    find_in_progress_run_for_response,
)
from helpers.webhook_scope import response_id_from_webhook_payload
from webhook_processors.abstract_webhook_processor import AbstractFoundryWebhookProcessor

_RESPONSE_TERMINAL_EVENTS = {
    "response.completed",
    "response.failed",
    "response.cancelled",
    "response.incomplete",
}


class ConversationWebhookProcessor(AbstractFoundryWebhookProcessor):
    """Completes ``invoke_agent`` runs correlated by Foundry ``response.*`` webhooks."""

    @classmethod
    def get_processor_type(cls) -> WebhookProcessorType:
        return WebhookProcessorType.ACTION

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return self.get_event_type(event.payload) in _RESPONSE_TERMINAL_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return []

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig | None
    ) -> WebhookEventRawResults:
        event_type = self.get_event_type(payload)
        response_id = response_id_from_webhook_payload(payload)
        if not response_id:
            logger.warning(f"Ignoring Foundry webhook without response id ({event_type})")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        run = await find_in_progress_run_for_response(response_id)
        if run is None:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )
        if not run.execution_properties.get("reportInvocationStatus", True):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        await complete_invoke_run_from_webhook(
            run,
            event_type=event_type,
            response_id=response_id,
        )
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
