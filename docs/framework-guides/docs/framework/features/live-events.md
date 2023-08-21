---
title: ⌛ Live Events
sidebar_position: 4
---

The Ocean framework provides convenient way to listen to events triggered by the third-party service and react to them
using webhook rest requests.

## Listening to webhook events

An Ocean integration needs to react and perform tasks based on events arriving from the 3rd-party service that it
integrates with.

Some 3rd-party services provide a way to configure a webhook that will send events to a URL of your choice. This is
usually the preferred way to listen to events from the 3rd-party service.

By configuring a webhook route in the integration and providing the URL to the 3rd-party service, the integration will
be able to listen to events from the 3rd-party service and react to them.

Upon receiving a request from the 3rd-party service, the integration will be able to perform any tasks it needs to
perform according to the event that was received. such as:

- Upsert a state of a resource from a specific kind
- Delete a resource from a specific kind
- Perform a full resync of all resources kinds
- Register gitops entities

## Configuring a webhook route

The ocean context provides a convenient way to configure a webhook route that will listen to events from the 3rd-party
using FastAPI router. Then the integration can use ocean functionality to react to the events.

The `ocean.router` provides a FastApi router that can be used to setup routes for the integration.

:::tip
The `ocean.router` is a FastAPI router, so you can use any Functionality that FastAPI usually provides.

As an example, you can use FastAPI's `Depends` to inject dependencies into your webhook route, or use FastAPI's
Pydantic models to validate the request body.

For more information about FastAPI, please refer to the [FastAPI documentation](https://fastapi.tiangolo.com/).
:::

:::note

All integration routes are prefixed with `/integration/`
So if you want to configure a webhook route for your integration, you should use the following
path: `/integration/webhook`

:::

```python
from port_ocean.context.ocean import ocean
from typing import Any


@ocean.router.post("/webhook")
async def webhook(data: dict[str, Any]):
    kind = extract_kind(data)
    if data['event'] == 'new':
        await ocean.register_raw(kind, [data])
    elif data['event'] == 'delete':
        await ocean.unregister_raw(kind, [data])
```

## Setting up the webhook in the 3rd-party service

It is recommended to setup the webhook in the 3rd-party service on the integration startup, so that the webhook will be
ready to receive events as soon as the integration starts.

For example, you can use the `ocean.on_start` decorator to register the webhook on the integration startup as such:

```python showLineNumbers
from port_ocean.context.ocean import ocean


@ocean.on_start()
async def register_webhook():
    await register_webhook_in_3rd_party_service()
```

As for the application host each integration can set the config parameter `appHost` which will be passed the integration
host url.
This parameter is optional and therefore the integration should handle the case where it is not set and the client does
not want to use the live events using webhook feature.
