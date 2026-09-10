from port_ocean.context.event import EventType, event_context
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from fake_org_data.fake_client import get_random_person_from_batch
from integration import ObjectKind
from webhook_processors.abstract_fake_webhook_processor import (
    AbstractFakeWebhookProcessor,
)
from webhook_processors.constants import FAKE_TASK_COMPLETED_EVENT


class FakePersonWebhookProcessor(AbstractFakeWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PERSON]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("event") != FAKE_TASK_COMPLETED_EVENT

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        person = await get_random_person_from_batch()
        async with event_context(EventType.HTTP_REQUEST, trigger_type="machine"):
            await ocean.register_raw(ObjectKind.PERSON, [person])
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
