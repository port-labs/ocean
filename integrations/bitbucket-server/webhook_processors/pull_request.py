from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventKind,
    WebhookEventRawResults,
)

from ..client import PR_WEBHOOK_EVENTS
from ..integration import ObjectKind
from ._base import BaseWebhookProcessorMixin


class PullRequestWebhookProcessor(BaseWebhookProcessorMixin):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers["x-event-key"] in PR_WEBHOOK_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PULL_REQUEST]

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:

        return WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[],
        )
