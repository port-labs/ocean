import asyncio
import os
from typing import List, Union, Callable, AsyncIterator, TypeVar, Any, Dict

import gitlab.exceptions
from gitlab import GitlabList, Gitlab
from gitlab.base import RESTObject, RESTObjectList
from gitlab.v4.objects import Project, ProjectPipelineJob, ProjectPipeline, Issue
from loguru import logger

T = TypeVar("T", bound=RESTObject)


class AsyncFetcher:
    def __init__(self, gitlab_client: Gitlab):
        self.gitlab_client = gitlab_client

    @staticmethod
    async def fetch(
        fetch_func: Callable[
            ...,
            Union[
                RESTObjectList,
                List[RESTObject],
                List[ProjectPipelineJob],
                List[ProjectPipeline],
                List[Issue],
                List[Dict[str, Any]],
                GitlabList,
                List[Project],
                List[Union[RESTObject, Dict[str, Any]]],
            ],
        ],
        validation_func: Callable[
            [Any],
            bool,
        ],
        batch_size: int = int(os.environ.get("GITLAB_BATCH_SIZE", 100)),
        **kwargs,
    ) -> AsyncIterator[
        Union[
            List[Union[RESTObject, Dict[str, Any]]],
            RESTObjectList,
            List[ProjectPipelineJob],
            List[ProjectPipeline],
            List[Issue],
            List[Project],
            List[RESTObject],
            List[Dict[str, Any]],
            GitlabList,
        ]
    ]:
        def fetch_batch(
            page_idx: int,
        ) -> Union[
            List[Union[RESTObject, Dict[str, Any]]],
            RESTObjectList,
            List[ProjectPipelineJob],
            List[ProjectPipeline],
            List[Issue],
            List[Project],
            List[RESTObject],
            List[Dict[str, Any]],
            GitlabList,
        ]:
            logger.info(f"Fetching page {page_idx}. Batch size: {batch_size}")
            return fetch_func(
                page=page_idx, per_page=batch_size, get_all=False, **kwargs
            )

        page = 1
        while True:
            batch = None
            try:
                batch = await asyncio.get_running_loop().run_in_executor(
                    None, fetch_batch, page
                )
            except gitlab.exceptions.GitlabListError as err:
                if err.response_code in (403, 404):
                    logger.warning(f"Failed to access resource, error={err}")
                    break
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
