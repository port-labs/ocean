from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from faker import Faker

fake = Faker()

WEBHOOK_PATH = "/webhook"


class FakePersonWebhookProcessor(AbstractWebhookProcessor):
    """Webhook processor for fake-person events"""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Simple authentication for fake integration - always return True"""
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that payload contains person-related data"""
        return True

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle person webhook events"""
        persons = payload["payload"]
        if payload.get("action") == "delete":
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=persons
            )
        return WebhookEventRawResults(
            updated_raw_results=persons, deleted_raw_results=[]
        )

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Determine if this processor should handle the event"""
        payload = event.payload
        return isinstance(payload, dict) and (
            "type" in payload
            and payload["type"] == "fake-person"
            and "action" in payload
            and payload["action"] in ["create", "update", "delete"]
            and "payload" in payload
            and isinstance(payload["payload"], list)
            and all(isinstance(item, dict) for item in payload["payload"])
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the resource kinds this event affects"""
        return ["fake-person"]


class FakeDepartmentWebhookProcessor(AbstractWebhookProcessor):
    """Webhook processor for fake-department events"""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Simple authentication for fake integration - always return True"""
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that payload contains department-related data"""
        return True

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle department webhook events"""
        departments = payload.get("payload")
        if payload.get("action") == "delete":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=departments,
            )
        return WebhookEventRawResults(
            updated_raw_results=departments,
            deleted_raw_results=[],
        )

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Determine if this processor should handle the event"""
        payload = event.payload
        return isinstance(payload, dict) and (
            "type" in payload
            and payload["type"] == "fake-department"
            and "action" in payload
            and payload["action"] in ["create", "update", "delete"]
            and "payload" in payload
            and isinstance(payload["payload"], list)
            and all(isinstance(item, dict) for item in payload["payload"])
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the resource kinds this event affects"""
        return ["fake-department"]


class FakeRepositoryWebhookProcessor(AbstractWebhookProcessor):
    """Webhook processor for fake-repository events"""

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        """Simple authentication for fake integration - always return True"""
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate that payload contains repository-related data"""
        return True

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle repository webhook events"""
        repositories = payload.get("payload")

        if payload.get("action") == "delete":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=repositories,
            )
        return WebhookEventRawResults(
            updated_raw_results=repositories,
            deleted_raw_results=[],
        )

    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Determine if this processor should handle the event"""
        payload = event.payload
        return isinstance(payload, dict) and (
            "type" in payload
            and payload["type"] == "fake-repository"
            and "action" in payload
            and payload["action"] in ["create", "update", "delete"]
            and "payload" in payload
            and isinstance(payload["payload"], list)
            and all(isinstance(item, dict) for item in payload["payload"])
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the resource kinds this event affects"""
        return ["fake-repository"]


def register_live_events_webhooks() -> None:
    """Register all live event webhook processors"""
    ocean.add_webhook_processor(WEBHOOK_PATH, FakePersonWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, FakeDepartmentWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, FakeRepositoryWebhookProcessor)
    logger.info("Registered fake integration webhook processors")
