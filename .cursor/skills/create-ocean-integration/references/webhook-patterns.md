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

# Event to Kind mapping (ObjectKind is defined in helpers/utils.py)
EVENT_KIND_MAP: dict[EventType, ObjectKind] = {
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

## Payload Validation Strategy

**Rule: Validate exactly what `handle_event` will access directly.**

The `validate_payload` method serves as a contract: if it returns `True`, then `handle_event` can safely access those fields using direct indexing `[]` instead of `.get()`.

### How to Decide What to Validate

1. **Write `handle_event` first** (or outline it) to identify which payload fields you access
2. **Validate those exact fields** in `validate_payload`
3. **Use `[]` indexing** in `handle_event` for validated fields (not `.get()`)

### Example: Trace Validation to Usage

```python
class ProjectWebhookProcessor(AbstractServiceWebhookProcessor):
    
    async def validate_payload(self, payload: EventPayload) -> bool:
        # Validate ONLY fields that handle_event will access directly
        # Use .get() in validation to avoid KeyError on malformed payloads
        
        if not payload.get("event_type"):
            return False
        
        project = payload.get("project")
        if not isinstance(project, dict):
            return False
        if not project.get("id"):
            return False
            
        return True
    
    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        # CORRECT: Use [] for validated fields - they are guaranteed to exist
        event_type = payload["event_type"]
        project_id = payload["project"]["id"]
        
        # WRONG: Don't use .get() for validated fields - it implies uncertainty
        # project_id = payload.get("project", {}).get("id")  # NO!
        
        if event_type == EventType.PROJECT_DELETED:
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[{"id": project_id}],
            )
        
        # Fetch full resource data
        client = ClientFactory.get_client()
        exporter = ProjectExporter(client)
        project = await exporter.get_single_resource(project_id)
        
        return WebhookEventRawResults(
            updated_raw_results=[project] if project else [],
            deleted_raw_results=[],
        )
```

### Validation Patterns

| Payload Structure | Validation in validate_payload (use .get()) | Usage in handle_event (use []) |
|-------------------|---------------------------------------------|-------------------------------|
| `payload["id"]` | `payload.get("id")` | `payload["id"]` |
| `payload["project"]["id"]` | `payload.get("project", {}).get("id")` | `payload["project"]["id"]` |
| `payload["action"]` | `payload.get("action") in VALID_ACTIONS` | `payload["action"]` |
| Optional field | Don't validate | `payload.get("description")` |

### Anti-Pattern: Using .get() for Validated Fields

```python
# BAD: Implies the field might not exist, but we validated it
async def handle_event(self, payload, resource_config):
    project_id = payload.get("project", {}).get("id")  # Wrong!
    if not project_id:  # Defensive code that shouldn't be needed
        return WebhookEventRawResults([], [])

# GOOD: Direct access for validated fields
async def handle_event(self, payload, resource_config):
    project_id = payload["project"]["id"]  # Correct - validated in validate_payload
```

## Resource Webhook Processor

```python
class ResourceWebhookProcessor(AbstractServiceWebhookProcessor):
    events = [EventType.RESOURCE_CREATED, EventType.RESOURCE_UPDATED]
    
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("event_type")
        return event_type in [e.value for e in self.events]
    
    async def validate_payload(self, payload: EventPayload) -> bool:
        # Use .get() to safely check fields that handle_event will access
        resource = payload.get("resource")
        if not isinstance(resource, dict):
            return False
        if not resource.get("id"):
            return False
        return True
    
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.RESOURCE]
    
    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        # Use [] indexing - fields were validated
        resource_id = payload["resource"]["id"]
        
        client = ClientFactory.get_client()
        exporter = ResourceExporter(client)
        
        resource = await exporter.get_single_resource(resource_id)
        return WebhookEventRawResults(
            updated_raw_results=[resource] if resource else [],
            deleted_raw_results=[],
        )
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
