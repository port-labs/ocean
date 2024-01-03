---
title: Performance
sidebar_label: 🏎️ Performance
sidebar_position: 5
---

import HttpxExample from '../\_common/httpx-instead-of-requests.md'

# 🏎️ Performance

This guide outlines the possible known performance enhancements that can be applied to an integration built using the
Ocean framework.

## Async work

Make sure to use async work whenever needed, for example, use async an implementation of 3rd party libraries.

### httpx instead of requests

For instance, use `httpx` instead of `requests`, httpx is an async implementation of the requests library and its usage makes sure that your integration does not block the event loop.

<HttpxExample />

## Python generators

Generators are a type of iterable in Python that allow you to iterate over a sequence of values without storing them all
in memory at once. They are a memory-efficient way to work with large datasets or when dealing with computations that
produce a stream of values. Generators are implemented using a special type of function called generator functions or by
using generator expressions.

```python showLineNumbers
def my_generator():
    for item in my_list:
        yield get_item_from_api(item)


gen = my_generator()

for value in gen:
    print(value)
```

n this example, `my_generator` is a generator function. Instead of using return, it uses the `yield` keyword to produce
values one at a time. When you iterate over the generator, each call to yield produces the next value in the sequence,
and the generator's state is preserved between calls.

### Generators in the Ocean framework

The Ocean framework provides a way to use generators in the integration `@ocean.on_resync` listeners.

Instead of returning a list of raw items, you can return a generator that will yield a list of items that will return
the data in batches. This allows the framework to start processing the data as soon as it is available and not wait
for the whole list to be returned.

This is especially useful when the integration is returning a large list of items or the integration needs to query paginated information which can be ingested in batches (for example, yielding one page response as a batch at a time to make sure the integration already starts ingesting entities to Port while the rest of the dataset is queried in the background)

:::tip
Try to optimize the amount of data that is being returned in each batch from the generator, this will make sure the integration is always working and passing the data from the 3rd-party to Port with no delay
:::

:::warning
Although using generators with Ocean can make the data appear faster, it will not make the integration faster, it will
only allow the framework to start processing the data as soon as it is available.

In general batch sizes should be optimized according to the performance seen both when querying the 3rd-party for information, and when examining Ocean's rate of ingestion to Port.

- A batch size that is too large can cause the integration to wait around too much without ingesting new entities, while also making the ingestion to Port slow due to the large single dataset
  - This will not cause a logical issue, it will only impact the integration's performance
- A batch size that is too small can cause rate-limiting issues when querying the 3rd-party
  - This could result in the integration not being functional

:::

In the following example, we are using a generator to fetch projects from an API that returns the data in batches.
Each batch will be yielded to the Ocean framework, which will ingest it into Port, while the integration processes the next batch.

```python showLineNumbers
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


@ocean.on_resync("Project")
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = MyIntegrationApiClient(ocean.integration_config["api_token"])

    async for projects in client.get_paginated_projects():
        yield projects
```
