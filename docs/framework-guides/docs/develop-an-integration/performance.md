---
title: 🏎️ Performance
sidebar_position: 7
---

import HttpxExample from '../_common/httpx-instead-of-requests.md'

This guide outlines the possible known performance enhancements that can be applied to an integration built using the
Ocean framework.

## Async work

Make sure to use async work whenever needed, for example, use async implementation of 3rd party libraries.

### httpx instead of requests

For instance, use `httpx` instead of `requests`, httpx is an async implementation of the requests library and by using
it you can make sure that your integration will not block the event loop.

<HttpxExample />

## Python generators

Generators are a type of iterable in Python that allow you to iterate over a sequence of values without storing them all
in memory at once. They are a memory-efficient way to work with large datasets or when dealing with computations that
produce a stream of values. Generators are implemented using a special type of function called generator functions or by
using generator expressions.

```python
def my_generator():
    for item in my_list:
        yield get_item_from_api(item)


gen = my_generator()

for value in gen:
    print(value)
```

n this example, my_generator is a generator function. Instead of using return, it uses the yield keyword to produce
values one at a time. When you iterate over the generator, each call to yield produces the next value in the sequence,
and the generator's state is preserved between calls.

### Generators in the Ocean framework

The Ocean framework provides a way to use generators in the integration `@ocean.on_resync` listeners.

Instead of returning a list of raw items, you can return a generator that will yield a list of items that will return
the data in batches. This will allow the framework to start processing the data as soon as it is available and not wait
for the whole list to be returned.

This is especially useful when the integration is returning a large list of items or need to fetch alot data from the
api that can be processed in batches or can be paginated from the api.

:::tip
Try to optimize the amount of data that is being returned in each batch from the generator, this will make the waiting
for the data fetching to be more seamless.
:::

:::caution
although using generators with ocean can make the data appear faster, it will not make the integration faster, it will
only allow the framework to start processing the data as soon as it is available.

Try to make batches as big as possible to allow more data to be processed in each batch, But not too big to make the
waiting for the data to be fetched not too long.
:::

In the following example, we are using a generator to fetch projects from an api that returns the data in batches.
Each batch will be processed an ingested accordingly to Port upon receiving it.

```python
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


@ocean.on_resync("Project")
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = MyIntegrationApiClient(ocean.integration_config["api_token"])

    async for projects in client.get_paginated_projects():
        yield projects
```
