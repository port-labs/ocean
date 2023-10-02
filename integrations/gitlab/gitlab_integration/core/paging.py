import os
import typing
import asyncio


class AsyncFetcher:
    def __init__(self, gitlab_client):
        self.gitlab_client = gitlab_client

    @staticmethod
    async def fetch(
        batch_size: int = os.environ.get("GITLAB_BATCH_SIZE", 100),
        fetch_func: typing.Callable = None,
        validation_func: typing.Callable = None,
        **kwargs,
    ) -> typing.AsyncIterator[typing.List[typing.Any]]:
        def fetch_batch(page: int):
            batch = fetch_func(page=page, per_page=batch_size, get_all=False, **kwargs)
            return batch

        page = 1
        while True:
            batch = await asyncio.get_running_loop().run_in_executor(
                None, fetch_batch, page
            )
            if not batch:
                break
            filtered_batch = []
            for item in batch:
                if validation_func is None or validation_func(item):
                    filtered_batch.append(item)
            yield filtered_batch

            page += 1
