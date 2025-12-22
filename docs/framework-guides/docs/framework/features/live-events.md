---
title: Live Events
sidebar_label: ⌛ Live Events
sidebar_position: 4
description: Use Ocean to process live events from 3rd-party services
---

# ⌛ Live Events

The Ocean framework provides convenient ways to listen to live events triggered by third-party services and react to them in real-time.

:::tip
Listening to live events is **optional**. For some third-party services, performing a full resync based on a schedule can be enough. In addition, some third-party services might not support outbound webhooks, which are necessary to support live events.
:::

## Overview

Live events allow your integration to receive real-time updates from third-party services when resources change. Ocean provides two approaches for handling live events:

1. **Live Event Processors (Recommended)** - Object-oriented approach with built-in queuing, workers, retries, and structured authentication
2. **Direct Endpoint Handlers (Legacy)** - Simple FastAPI route handlers for basic use cases

## Approach 1: Live Event Processors (Recommended)

The recommended approach uses **live event processors** - classes that extend `AbstractWebhookProcessor`. This approach provides:

- ✅ **Asynchronous processing** with worker queues
- ✅ **Built-in retry logic** with exponential backoff
- ✅ **Structured authentication and validation**
- ✅ **Event filtering** to determine which events to process
- ✅ **Multiple processors** per endpoint for different resource kinds
- ✅ **Better error handling** and cancellation support

### Creating a Live Event Processor

To create a live event processor, extend `AbstractWebhookProcessor` and implement the required methods:

```python showLineNumbers
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

class IssueLiveEventProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        """Determine if this processor should handle the event"""
        return event.payload.get("event_type", "").startswith("issue_")

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        """Return the resource kinds this event affects"""
        return ["issue"]

    async def authenticate(
        self, payload: EventPayload, headers: EventHeaders
    ) -> bool:
        """Verify the request is legitimate"""
        # Implement your authentication logic here
        # e.g., verify signature, check API key, etc.
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Ensure the payload is valid"""
        # Implement your validation logic here
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Process the event and return results"""
        # Fetch updated data from the third-party service
        issue_id = payload["issue"]["id"]
        updated_issue = await fetch_issue_from_api(issue_id)

        if payload.get("event_type") == "issue_deleted":
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[payload["issue"]],
            )

        return WebhookEventRawResults(
            updated_raw_results=[updated_issue],
            deleted_raw_results=[],
        )
```

### Registering Live Event Processors

Register processors in your `main.py` file:

```python showLineNumbers
from port_ocean.context.ocean import ocean
from webhook_processors.issue_webhook_processor import IssueLiveEventProcessor
from webhook_processors.project_webhook_processor import ProjectLiveEventProcessor

# Register processors for the same endpoint
# Ocean will route events to the appropriate processor based on should_process_event()
ocean.add_webhook_processor("/webhook", IssueLiveEventProcessor)
ocean.add_webhook_processor("/webhook", ProjectLiveEventProcessor)
```

:::note
Ocean prefixes integration routes with `/integration/`.

For example, if you register a processor for `/webhook`, the Ocean framework will expose the path: `/integration/webhook`.
:::

### Processor Configuration

Processors support configurable retry behavior:

```python showLineNumbers
class MyLiveEventProcessor(AbstractWebhookProcessor):
    max_retries = 5  # Maximum number of retries
    initial_retry_delay_seconds = 1.0  # Initial delay before first retry
    max_retry_delay_seconds = 30.0  # Maximum delay between retries
    exponential_base_seconds = 2.0  # Base for exponential backoff

    # ... rest of implementation
```

For detailed implementation examples, see the [Implementing Live Events](../../developing-an-integration/implementing-live-events.md) guide.

## Approach 2: Direct Endpoint Handlers (Legacy)

For simple use cases, you can use direct FastAPI route handlers. This approach is simpler but lacks the advanced features of processors:

- ⚠️ No built-in queuing or workers
- ⚠️ No automatic retry logic
- ⚠️ Manual error handling required
- ✅ Simple and straightforward for basic scenarios

### Creating a Direct Endpoint Handler

Use `ocean.router` to create a FastAPI route:

```python showLineNumbers
from port_ocean.context.ocean import ocean
from typing import Any

@ocean.router.post("/webhook")
async def webhook_handler(data: dict[str, Any]):
    """Handle live events directly"""
    kind = extract_kind(data)
    if data['event'] == 'new':
        await ocean.register_raw(kind, [data])
    elif data['event'] == 'delete':
        await ocean.unregister_raw(kind, [data])
```

:::tip
The `ocean.router` is a FastAPI router, so you can use any functionality that FastAPI provides.

As an example, you can use FastAPI's `Depends` to inject dependencies into your route, or use FastAPI's Pydantic models to validate the request body.

For more information about FastAPI, please refer to the [FastAPI documentation](https://fastapi.tiangolo.com/).
:::

:::note
Ocean prefixes integration routes with `/integration/`.

For example, if you configure the integration to listen to the `/webhook` endpoint, the Ocean framework will expose the path: `/integration/webhook`.
:::

## Setting Up Live Events in Third-Party Services

It's recommended to set up the webhook/endpoint in the third-party service on integration startup, so it's ready to receive events as soon as the integration starts.

Use the `ocean.on_start` decorator to register the webhook on integration startup:

```python showLineNumbers
from port_ocean.context.ocean import ocean

@ocean.on_start()
async def register_live_events_endpoint():
    """Register the live events endpoint with the third-party service"""
    await register_webhook_in_3rd_party_service()
```

### Dynamic Configuration

Each integration can set the `baseUrl` [config parameter](../../developing-an-integration/testing-the-integration.md) which contains the integration host URL.

This parameter is optional, so handle the case where it's not set:

```python showLineNumbers
from port_ocean.context.ocean import ocean

@ocean.on_start()
async def register_live_events_endpoint():
    # highlight-next-line
    if ocean.integration_config.get("app_host") is not None:
        # An appHost parameter was provided to the integration
        # so we can setup the third-party webhook
        await register_webhook_in_3rd_party_service()
```

## When to Use Each Approach

**Use Live Event Processors when:**
- You need reliable processing with retries
- You want structured authentication and validation
- You need to handle multiple resource kinds from the same endpoint
- You want built-in queuing and worker support
- You're building a production integration

**Use Direct Endpoint Handlers when:**
- You have very simple event handling logic
- You don't need retry logic or queuing
- You're prototyping or building a simple integration
- You want full control over the request handling

:::tip Migration
If you're currently using direct endpoint handlers and need more reliability or features, consider migrating to live event processors. The processor approach provides better error handling, retries, and scalability.
:::

## What Happens When Events Are Received

When your integration receives a live event:

1. **Event Reception** - Ocean receives the HTTP POST request
2. **Routing** - For processors, Ocean routes to matching processors based on `should_process_event()`
3. **Authentication & Validation** - Processors verify the request and validate the payload
4. **Processing** - The event is processed (fetching updated data, etc.)
5. **Port Update** - Results are transformed using JQ mappings and applied to Port

For more details on the architecture, see the [Live Events Processing Architecture](../architecture/live-events.md) guide.
