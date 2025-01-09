import typing

import aiostream

if typing.TYPE_CHECKING:
    from asyncio import Semaphore


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


async def semaphore_async_iterator(
    semaphore: "Semaphore",
    function: typing.Callable[[], typing.AsyncIterator[typing.Any]],
) -> typing.AsyncIterator[typing.Any]:
    """
    Executes an asynchronous iterator function under a semaphore to limit concurrency.

    This function ensures that the provided asynchronous iterator function is executed
    while respecting the concurrency limit imposed by the semaphore. It acquires the
    semaphore before executing the function and releases it after the function completes,
    thus controlling the number of concurrent executions.

    Parameters:
        semaphore (asyncio.Semaphore | asyncio.BoundedSemaphore): The semaphore used to limit concurrency.
        function (Callable[[], AsyncIterator[Any]]): A nullary asynchronous function, - apply arguments with `functools.partial` or an anonymous function (lambda)
            that returns an asynchronous iterator. This function is executed under the semaphore.

    Yields:
        Any: The items yielded by the asynchronous iterator function.

    Usage:
        ```python
        import asyncio

        async def async_iterator_function(param1, param2):
            # Your async code here
            yield ...

        async def async_generator_function():
            # Your async code to retrieve items
            param1 = "your_param1"
            yield param1

        async def main():
            semaphore = asyncio.BoundedSemaphore(50)
            param2 = "your_param2"

            tasks = [
                semaphore_async_iterator(
                    semaphore,
                    lambda: async_iterator_function(param1, param2) # functools.partial(async_iterator_function, param1, param2)
                )
                async for param1 in async_generator_function()
            ]

            async for batch in stream_async_iterators_tasks(*tasks):
                # Process each batch
                pass

        asyncio.run(main())
        ```
    """
    async with semaphore:
        async for result in function():
            yield result
