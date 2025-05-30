---
title: Sync Entities State
sidebar_label: 🔁 Sync Entities State
sidebar_position: 2
description: Use Ocean to keep the catalog up to date
---

# 🔁 Sync Entities State

The Ocean framework provides a way to sync entities state between the 3rd-party application and Port. This can be done using the Ocean **sync** and **raw sync** functionality.

The following functions are used to check state of entities in Port vs the state of entities and objects reported by the 3rd-party service. Based on the difference between these two states, the integration will generate a set of create, update and delete requests to Port's API, that will sync the two states.

- [`ocean.on_resync`](#oceanon_resync)
- [`ocean.sync_raw_all`](#oceansync_raw_all)
- [`ocean.sync`](#oceansync)

:::note
The integration will only interact with entities in Port that match its user agent. This means these are entities that were either created or updated by the integration during their lifecycle.

For more information refer to the [user agent](./user-agent.md) page.
:::

## Ocean raw sync

Ocean raw sync is a simple way to sync entities state into Port.

The Ocean raw sync functionality uses the integration [resource mapping](./resource-mapping.md) specified by the end user to transform the 3rd-party raw data into Port entities, by leveraging the JQ expressions specified in the resource mapping applying them to the raw data received from the 3rd-party.

By default, Ocean will perform a raw sync on all data returned from the `@ocean.on_resync` listener functions. In these functions,
the integration needs to return a list of raw data (dictionaries) that the end user will be able to transform into
Port entities using the [resource mapping](./resource-mapping.md).

The [Ocean context](./contexts.md#ocean-context) provides multiple functions that can be used to help to sync raw data into
Port:

### `@ocean.on_resync()`

A decorator used to wrap the function that will be called when the integration receives a resync event.

The wrapped function will need to return a list of raw data (dictionaries) that will be transformed into
Port entities.

By default, the decorated function will be used to process all `kind`s specified in the integration's [resource mapping](./resource-mapping.md) (the default value to filter kinds is `*`).

It is possible to create a separate function that will handle a specific `kind` by passing the `kind` argument to the decorator.

```python showLineNumbers
from port_ocean.context.ocean import ocean

# The following function will be called and used to process only
# resources of the "SpecialKind" during every resync event
@ocean.on_resync("SpecialKind")
def special_kind_resync(kind: str):
    return [...]  # List of raw dictionaries from the 3rd party application

# The following function will be called and used to process all kinds during every resync event
@ocean.on_resync()
def generic_resync(kind: str):
    if kind == "SpecialKind":
        return []
    return [...]  # List of raw dictionaries from the 3rd party application
```

:::tip
As shown in the [Performance](../../developing-an-integration/performance.md#generators-in-the-ocean-framework) page, it is recommended to use the `@ocean.on_resync` decorator and return a generator with the results (using the `yield` keyword) to avoid blocking the event loop and improve integration performance.

For simplicity, the examples above show usage of the decorator using the `return` keyword.
:::

### `ocean.sync_raw_all`

The `ocean.sync_raw_all` function checks the current state of Port entities managed by the integration, then it calls all of the functions decorated with the [`@ocean.on_resync()`](#oceanon_resync) decorator to perform a complete resync between the state in Port and the state in the 3rd-party service.

```python showLineNumbers
from port_ocean.context.ocean import ocean

# Whenever a POST request is made to the "/integration/my-custom-resync" route of the integration,
# a complete resync will occur
@ocean.router.post("/my-custom-resync")
def my_custom_resync():
    ocean.sync_raw_all()
```

:::note
This function starts a complete `resync` event calls all of the decorated functions, therefore it is recommended to
use this function only when the integration needs to resync the state for all of the entities from all of the `kind`s.
:::

### `ocean.update_raw_diff`

The `ocean.update_raw_diff` function is used to calculate the difference between 2 given states and apply it to Port.

The function receives 2 arguments:

1. `kind` - a string that specifies the kind of entities to perform the update for, will be used to find the relevant [resource mapping](./resource-mapping.md)
2. `raw_diff` - a dictionary that contains 2 keys - `before` and `after` that contain the desired state of known entities before and after the update respectively

The function will generate a list of create, update and delete requests based on the `raw_diff` and apply the requests to Port to sync the entities state.

```python showLineNumbers
from port_ocean.context.ocean import ocean


@ocean.router.post("/sync")
def sync_webhook():
    # Fetch the raw data from the 3rd party application
    raw_data = [...]  # List of raw dictionaries from the 3rd party application

    # Calculate the difference between the current state and the desired state
    ocean.update_raw_diff("MyKind", {
        "before": [...],  # List of raw dictionaries from Port
        "after": raw_data
    })
```

<!-- TODO: fix -->

:::note
The `ocean.update_raw_diff` function will not affect entities that are not defined in the given states.
Therefore, if the integration is syncing a list of entities, the function will not delete entities that are not
defined in the before state and missing in the after state.
:::

:::tip
An empty list can be passed to the `before` or `after` keys to indicate that there is no state for the given kind,
and therefore all the entities in the other state will be created or deleted accordingly.
:::

### `ocean.register_raw`

The `ocean.register_raw` function transforms the given data into Port entities without taking the existing state into consideration, the function will only create or update entities in Port based on the list of dictionaries passed to it and the resource mapping matching the input `kind`:

```python showLineNumbers
from port_ocean.context.ocean import ocean


@ocean.router.post("/sync")
def sync_webhook():
    # Fetch the raw data from the 3rd party application
    raw_data = [...]  # List of raw dictionaries from the 3rd party application

    # Register the raw data into Port
    ocean.register_raw("MyKind", raw_data)
```

### `ocean.unregister_raw`

The `ocean.unregister_raw` function transforms the given data into Port entities without taking the existing state into consideration, the function will only delete entities in Port based on the list of dictionaries passed to it and the resource mapping matching the input `kind`:

```python showLineNumbers
from port_ocean.context.ocean import ocean


@ocean.router.post("/sync")
def sync_webhook():
    # Fetch the raw data from the 3rd party application
    raw_data = [...]  # List of raw dictionaries from the 3rd party application

    # Unregister the raw data from Port
    ocean.unregister_raw("MyKind", raw_data)
```

## Ocean sync

The Ocean sync functions provide equivalent functionality to their [raw sync](#ocean-raw-sync) counterparts. The difference is that the sync functions expect objects that already match the format of Port entities.

:::tip
Since these functions receive proper entities, there is no need to specify the `kind` parameter.
:::

### `ocean.update_diff`

Equivalent to [`ocean.update_raw_diff`](#oceanupdate_raw_diff)

```python showLineNumbers
from port_ocean.context.ocean import ocean
from port_ocean.core.models import Entity


@ocean.router.post("/sync")
def sync_webhook():
    entities = [Entity(...)]  # List of constructed entities

    # Calculate the difference between the current state and the desired state
    ocean.update_diff({
        "before": [...],
        "after": entities
    })
```

### `ocean.register`

Equivalent to [`ocean.register_raw`](#oceanregister_raw)

```python showLineNumbers
from port_ocean.context.ocean import ocean
from port_ocean.core.models import Entity


@ocean.router.post("/sync")
def sync_webhook():
    entities = [Entity(...)]  # List of constructed entities

    # Register the entities into Port
    ocean.register(entities)
```

### `ocean.unregister`

Equivalent to [`ocean.unregister_raw`](#oceanunregister_raw)

```python showLineNumbers
from port_ocean.context.ocean import ocean
from port_ocean.core.models import Entity


@ocean.router.post("/sync")
def sync_webhook():
    entities = [Entity(...)]  # List of constructed entities

    # Register the entities into Port
    ocean.unregister(entities)
```

### `ocean.sync`

The `ocean.sync` function receives a list of Port entity objects, it calculates the difference between the given list and the state in Port and then applies the necessary changes to Port.

```python showLineNumbers
from port_ocean.context.ocean import ocean
from port_ocean.core.models import Entity


@ocean.router.post("/sync")
def sync_webhook():
    entities = [Entity(...)]  # List of constructed entities

    # Sync the entities into Port
    ocean.sync(entities)
```
