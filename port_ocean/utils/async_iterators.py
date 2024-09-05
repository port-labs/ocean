import typing

import aiostream


async def stream_async_iterators_tasks(
    *tasks: typing.AsyncIterable[typing.Any],
) -> typing.AsyncIterable[typing.Any]:
    """
    This function takes a list of async iterators and streams the results of each iterator as they are available.
    By using this function you can combine multiple async iterators into a single stream of results, instead of waiting
    for each iterator to finish before starting the next one.

    Usage:
    ```python
    async def async_iterator1():
        for i in range(10):
            yield i
            await asyncio.sleep(1)

    async def async_iterator2():
        for i in range(10, 20):
            yield i
            await asyncio.sleep(1)

    async def main():
        async for result in stream_async_iterators_tasks([async_iterator1(), async_iterator2()]):
            print(result)
    ```

    Caution - Before using this function, make sure that the third-party API you are calling allows the number of
    concurrent requests you are making. If the API has a rate limit, you may need to adjust the number of concurrent
    requests to avoid hitting the rate limit.

    :param tasks: A list of async iterators
    :return: A stream of results
    """
    if not tasks:
        return

    if len(tasks) == 1:
        async for batch_items in tasks[0]:
            yield batch_items
        return

    combine = aiostream.stream.merge(tasks[0], *tasks[1:])
    async with combine.stream() as streamer:
        async for batch_items in streamer:
            yield batch_items
