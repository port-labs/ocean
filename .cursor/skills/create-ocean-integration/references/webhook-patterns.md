# Webhook Patterns

## Event-to-Kind Mapping

Map each webhook event type to the corresponding ObjectKind:

```python
# webhook/events.py
from enum import StrEnum

class EventType(StrEnum):
    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"
    PROJECT_DELETED = "project.deleted"
    ISSUE_CREATED = "issue.created"
    ISSUE_UPDATED = "issue.updated"

# Event to Kind mapping
EVENT_KIND_MAP: dict[EventType, str] = {
    EventType.PROJECT_CREATED: ObjectKind.PROJECT,
    EventType.PROJECT_UPDATED: ObjectKind.PROJECT,
    EventType.PROJECT_DELETED: ObjectKind.PROJECT,
    EventType.ISSUE_CREATED: ObjectKind.ISSUE,
    EventType.ISSUE_UPDATED: ObjectKind.ISSUE,
}

# Events that trigger deletion vs upsert
DELETE_EVENTS = {EventType.PROJECT_DELETED}
```

Use this mapping in webhook processors to route events correctly.

## Base Webhook Processor Structure

```python
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.context.event import event
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, EventHeaders

class AbstractServiceWebhookProcessor(AbstractWebhookProcessor):
    """Base processor with signature verification."""
    
    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True  # Verification happens in should_process_event
    
    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not await self._should_process_event(event):
            return False
        return self._verify_signature(event)
    
    def _verify_signature(self, event: WebhookEvent) -> bool:
        webhook_secret = ocean.integration_config.get("webhook_secret")
        if not webhook_secret:
            return True  # No secret configured
        
        signature = event.headers.get("x-signature-header")
        if not signature:
            logger.warning("Missing signature header")
            return False
        
        expected = hmac.new(
            webhook_secret.encode(),
            event.body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected)
    
    @abstractmethod
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        pass
```

## Resource Webhook Processor

```python
class ResourceWebhookProcessor(AbstractServiceWebhookProcessor):
    events = [EventType.RESOURCE_CREATED, EventType.RESOURCE_UPDATED]
    
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("event_type")
        return event_type in [e.value for e in self.events]
    
    async def get_matching_kinds(self, event: WebhookEvent) -> List[str]:
        return [ObjectKind.RESOURCE]
    
    async def handle_event(
        self, payload: Dict[str, Any], resource_config: ResourceConfig
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        resource_id = payload.get("resource_id")
        
        client = create_client()
        exporter = ResourceExporter(client)
        
        resource = await exporter.get_resource(resource_id)
        if resource:
            yield [resource]
```

## Webhook Registration

```python
# main.py or webhook/registry.py
WEBHOOK_PATH = "/webhook"

def register_webhooks() -> None:
    ocean.add_webhook_processor(WEBHOOK_PATH, ResourceWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, AnotherResourceProcessor)
```

## Verification Patterns by Provider

| Provider | Header | Format | Algorithm |
|----------|--------|--------|-----------|
| GitHub | `x-hub-signature-256` | `sha256=...` | HMAC-SHA256 |
| Okta | `Authorization` | Custom token | String match |
| Generic | `x-signature` | Hex digest | HMAC-SHA256 |

## Webhook Challenge Verification

Some providers (Okta, Slack) verify webhook URLs with a challenge:

```python
# integration.py
class CustomLiveEventsProcessorManager(LiveEventsProcessorManager):
    def _register_route(self, path: str) -> None:
        @ocean.app.router.api_route(path, methods=["GET", "POST"])
        async def handle_webhook(request: Request):
            if request.method == "GET":
                # Handle verification challenge
                challenge = request.headers.get("x-verification-challenge")
                if challenge:
                    return {"verification": challenge}
            
            # Normal POST handling
            event = await WebhookEvent.from_request(request)
            await self._event_queues[path].put(event)
            return {"status": "ok"}
```
