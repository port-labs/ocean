---
title: Live Events
sidebar_label: ⌛ Live Events
sidebar_position: 4
description: Use Ocean to process live events from 3rd-party services
---

# ⌛ Live Events

The Ocean framework provides convenient way to listen to events triggered by the third-party service and react to them
using webhook REST requests.

:::tip
Listening to live events is **optional**, for some 3rd-party services, performing a full-resync based on a schedule can be enough. In addition, some 3rd-party services might not support outbound webhooks, which are necessary to support live events.
:::

## Listen to webhook events

To handle live events, an Ocean integration needs to react and perform tasks based on events arriving from the 3rd-party service that it
integrates with.

The most common method for an integration to receive and react to live events is to configure a webhook.

In this method, the Ocean integration has code exposing a URL endpoint that receives events sent from the 3rd-party service in the form of an outbound webhook that contains the information of the latest event.

By configuring a webhook route in the integration and providing the URL to the 3rd-party service, the integration will
be able to listen to events from the 3rd-party service and react to them.

Upon receiving a request from the 3rd-party service, the integration will be able to perform any tasks it needs to perform according to the event that was received. such as:

- Update a catalog resource of a specific kind
- Delete a catalog resource of a specific kind
- Perform a full resync of all resources kinds
- Register GitOps entities
- etc

## Configure a webhook route

The Ocean context provides a convenient way to configure a webhook route that will listen to events from the 3rd-party
using the FastAPI router. Once the webhook route is setup the integration can use Ocean functionality to react to the events.

The `ocean.router` provides a FastAPI router that can be used to setup routes for the integration.

:::tip
The `ocean.router` is a FastAPI router, so you can use any Functionality that FastAPI usually provides.

As an example, you can use FastAPI's `Depends` to inject dependencies into your webhook route, or use FastAPI's
Pydantic models to validate the request body.

For more information about FastAPI, please refer to the [FastAPI documentation](https://fastapi.tiangolo.com/).
:::

:::note

Ocean prefixes integration routes with `/integration/`.

For example, if you configure the integration to listen to the `/webhook` endpoint, the Ocean framework will expose the path: `/integration/webhook`.

:::

Here is an example definition that exposes a `/integration/webhook` route the integration will listen to:

```python showLineNumbers
from port_ocean.context.ocean import ocean
from typing import Any

# This decorator defines the URL endpoint of the integration as `/integration/webhook`
# highlight-next-line
@ocean.router.post("/webhook")
async def webhook(data: dict[str, Any]):
    kind = extract_kind(data)
    if data['event'] == 'new':
        await ocean.register_raw(kind, [data])
    elif data['event'] == 'delete':
        await ocean.unregister_raw(kind, [data])
```

## Setup the webhook in the 3rd-party service

It is recommended to setup the webhook in the 3rd-party service on integration startup, that way the webhook will be
ready to receive events as soon as the integration starts.

For example, you can use the `ocean.on_start` decorator to register the webhook on integration startup:

```python showLineNumbers
from port_ocean.context.ocean import ocean


@ocean.on_start()
async def register_webhook():
    await register_webhook_in_3rd_party_service()
```

As for the application host each integration can set the [config parameter](../../develop-an-integration/integration-configuration.md) `appHost` which contains the integration
host url.

This parameter is optional and therefore the integration should handle the case where it is not set and the client does
not want to use the live events using webhook feature.

Here is a simple example that shows how to dynamically handle the webhook setup in case the `appHost` configuration parameter is passed to the integration:

```python showLineNumbers
from port_ocean.context.ocean import ocean


@ocean.on_start()
async def register_webhook():
    # highlight-next-line
    if ocean.integration_config.get("app_host") is not None:
        # An appHost parameter was provided to the integration
        # so we can setup the 3rd-party webhook
        await register_webhook_in_3rd_party_service()
```
