---
title: 🧩 Contexts
sidebar_position: 3
---

The Ocean framework provides a built-in thread-safe global variables store that holds relevant context information for the
integration.

## Ocean context

The Ocean context is available to the integration code and can be used to simplify the work of the integration
developer.

The Ocean context holds the Ocean app along with aliases to ocean functionality, and can be accessed using the `ocean`
variable.

### Context information

Using the Ocean context, the integration can access the following functionality:

- `ocean.config`: The integration configuration
- `ocean.router`: A FastAPI router that can be used to expose integration endpoints
- `ocean.integration`: The integration class that provides all the out of the box functionality of an Ocean integration
- `ocean.port_client`: A Port client the Ocean framework uses to communicate with Port's API
- `ocean.on_resync`: A decorator that can be used to register a function to be called when a resync is requested
- `ocean.on_start`: A decorator that can be used to register a function to be called when the integration starts
- And more methods that can be used to sync, register, unregister resources

### Example

Here is an example snippet showing how to use some of the functions provided by the `ocean` context:

```python showLineNumbers
from typing import Any

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


# highlight-next-line
@ocean.on_resync("Issue")
async def on_resync_kind(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
  # handle the request to resync catalog items of a specific kind
  ...


# highlight-next-line
@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> None:
  # handle an event sent to the integration's app host to the `/integration/webhook` route

  # Get the value of the appHost parameter from the integration config
  # highlight-next-line
  integration_app_host = ocean.integration_config.get("app_host")
  await ocean.register_raw("myKind", [data])


# Called once when the integration starts.
# highlight-next-line
@ocean.on_start()
async def on_start() -> None:
  # integration startup logic
  ...
```

## Event context

An event is a representation of an execution of the integration code. Event examples:

- **Resync event**: an event that is triggered when the integration is requested to perform a full
  resync of all resource kinds.
- **Any Rest Event**: an event that is triggered when an HTTP request to one of the integration
  endpoints is received.

You can access the event context using the `event` variable.

The event variable is accessible only when the integration code is executed as a result of an event.

The event context is available to the integration code and can be used to simplify the work of the integration developer
when trying to access event related data.

### Context information

Using the event context, the integration can access the following information:

- `event.type`: the type of the event. For example: `resync`, `start`, `http_request`
- `event.triggerType`: the trigger type of the event. For example: `manual`, `machine`, `request`
- `event.resource_config`: when the event is a resync event, the `resource_config` holds the resource mapping configuration for the
  resync
- `event.port_app_config`: when the event is a resync event, the `port_app_config` holds the PortAppConfig used for the resync
- `event.attributes`: a dictionary of attributes that can be used to pass data between different parts of the integration
  code. The `attributes` dictionary can also be used as a cache to avoid performing the same query or data calculation twice in the context of the same event, and saving the results directly in the `attributes` for later usage in the event processing

### Example

Here is an example snippet showing how to access the data provided by the `event` context:

```python showLineNumbers
from port_ocean.context.event import event

app_config = event.port_app_config
event_type = event.type
event_trigger_type = event.trigger_type
```
