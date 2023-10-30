import asyncio
import os
from typing import List, Union, Callable, AsyncIterator, TypeVar, Any, Dict

from gitlab.base import RESTObject, RESTObjectList
from loguru import logger

T = TypeVar("T", bound=RESTObject)


class AsyncFetcher:
    def __init__(self, gitlab_client):
        self.gitlab_client = gitlab_client

    @staticmethod
    async def fetch(
        fetch_func: Callable[
            ..., Union[RESTObjectList, List[RESTObject], List[Dict[str, Any]]]
        ],
        batch_size: int = int(os.environ.get("GITLAB_BATCH_SIZE", 100)),
        validation_func: Callable[[T], bool] | None = None,
        **kwargs,
    ) -> AsyncIterator[List[T]]:
        def fetch_batch(page_idx: int):
            logger.info(f"Fetching page {page_idx}. Batch size: {batch_size}")
            return fetch_func(
                page=page_idx, per_page=batch_size, get_all=False, **kwargs
            )

        page = 1
        while True:
            batch = await asyncio.get_running_loop().run_in_executor(
                None, fetch_batch, page
            )
            if not batch:
                logger.info(f"No more items to fetch after page {page}")
                break
            logger.info(f"Queried {len(batch)} items before filtering")
            filtered_batch = []
            for item in batch:
                if validation_func is None or validation_func(item):
                    filtered_batch.append(item)
            yield filtered_batch

            page += 1
