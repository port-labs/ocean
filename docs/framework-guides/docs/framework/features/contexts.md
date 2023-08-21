---
title: 🧩 Contexts
sidebar_position: 3
---

The Ocean framework provides a built-in thread-safe global variables that store relevant context information for the
integration.

The context is available to the integration code and can be used to simplify the work of the integration developer.

### Ocean context

The Ocean context is available to the integration code and can be used to simplify the work of the integration
developer.

The Ocean context holds the Ocean app along with aliases to ocean functionality, and can be accessed using the `ocean`
variable.

Using the Ocean context, the integration can access the following functionality:

- `ocean.config`: The integration configuration
- `ocean.router`: A FastAPI router that can be used to expose integration endpoints
- `ocean.integration`: The integration class holding all the out of the box functionality of ocean integration
- `ocean.port_client`: A Port client the ocean app uses to communicate with the Port API
- `ocean.on_resync`: A decorator that can be used to register a function to be called when a resync is requested
- `ocean.on_start`: A decorator that can be used to register a function to be called when the integration starts
- And more methods that can be used to sync, register, unregister resources

### Event context

An event is a representation of an execution of the integration code. Examples for event are:

- **A resync event**: A resync event is an event that is triggered when the integration is requested to perform a full
  resync of all resources kinds.
- **Any Rest Event**: A rest event is an event that is triggered when there was an http request to one of the integration
  endpoints.

You can access the event context using the `event` variable.

The event variable is accessed only when the integration code is executed as a result of an event.

The event context is available to the integration code and can be used to simplify the work of the integration developer
when trying to access an event related data.

Using the event context, the integration can access the following information:

- `event.type`: The type of the event. For example: `resync`, `start`, `http_request`
- `event.triggerType`: The trigger type of the event. For example: `manual`, `machine`, `request`
- `event.resource_config`: When the event is a resync event, this will hold the resource mapping configuration for the
  resync.
- `event.port_app_config`: When the event is a resync event, this will hold the while PortAppConfig for the resync.
- `event.attributes`: A dictionary of attributes that can be used to pass data between different parts of the integration
  code. (Can be used to store cache for the specific event context and will be accessed only by the specific event)

