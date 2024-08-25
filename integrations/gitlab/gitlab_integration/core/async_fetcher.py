import asyncio
from asyncio import get_event_loop
from concurrent.futures import ThreadPoolExecutor
from typing import List, Union, Callable, AsyncIterator, TypeVar, Any, Dict

import gitlab.exceptions
from gitlab import GitlabList
from gitlab.base import RESTObject, RESTObjectList
from gitlab.v4.objects import (
    Project,
    ProjectPipelineJob,
    ProjectPipeline,
    Issue,
    Group,
    ProjectFile,
)
from loguru import logger

from port_ocean.core.models import Entity

T = TypeVar("T", bound=RESTObject)

DEFAULT_PAGINATION_PAGE_SIZE = 100
FIRST_PAGE = 1


class AsyncFetcher:
    @staticmethod
    async def fetch_single(
        fetch_func: Callable[
            ...,
            Union[
                RESTObject,
                ProjectPipelineJob,
                ProjectPipeline,
                Issue,
                Project,
                Group,
            ],
        ],
        *args,
    ) -> Union[
        RESTObject,
        RESTObject,
        ProjectPipelineJob,
        ProjectPipeline,
        Issue,
        Project,
        Group,
        ProjectFile,
    ]:
        with ThreadPoolExecutor() as executor:
            return await get_event_loop().run_in_executor(executor, fetch_func, *args)

    @staticmethod
    async def fetch_batch(
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
        page_size: int = DEFAULT_PAGINATION_PAGE_SIZE,
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
        def fetch_page(
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
            logger.info(f"Fetching page {page_idx}. Page size: {page_size}")
            return fetch_func(
                page=page_idx, per_page=page_size, get_all=False, **kwargs
            )

        page = 1
        while True:
            batch = None
            try:
                batch = await asyncio.get_running_loop().run_in_executor(
                    None, fetch_page, page
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

    @staticmethod
    async def fetch_entities_diff(
        gitlab_service,
        project: Project,
        spec_path: str | List[str],
        before: str,
        after: str,
        ref: str,
    ) -> tuple[list[Entity], list[Entity]]:
        with ThreadPoolExecutor() as executor:
            return await get_event_loop().run_in_executor(
                executor,
                gitlab_service.get_entities_diff,
                project,
                spec_path,
                before,
                after,
                ref,
            )

    def _parse_file_metadata(self, file: dict[str, Any]) -> dict[str, Any]:
        return {"path": file["path"], "type": file["type"]}

    async def filter_repository_tree(
        self,
        project: Project,
        filtering_callable: None | Callable[..., bool] = None,
        filtering_paths: list[str] = [],
        ref: str = "",
        recursive: bool = False,
        **kwargs: Any,
    ) -> GitlabList | List[Dict[str, Any]]:
        with ThreadPoolExecutor() as executor:

            def fetch_func() -> Any:
                current_page_id = FIRST_PAGE
                files: List[Dict[str, Any]] = []
                while True:
                    try:
                        logger.info(
                            f"Requesting page {current_page_id} of project {project.path_with_namespace}, Currently found {len(files)} relevant files / directories.."
                        )
                        page_files = project.repository_tree(
                            ref=ref,
                            recursive=recursive,
                            page=current_page_id,
                            per_page=DEFAULT_PAGINATION_PAGE_SIZE,
                            **kwargs,
                        )
                        if not page_files:
                            logger.info(
                                f"Done iterating file pages for project {project.path_with_namespace}, Found {len(files)} relevant files.."
                            )
                            return files
                        if filtering_paths and filtering_callable:
                            for file in page_files:
                                if filtering_callable(
                                    filtering_paths, file["path"] or ""
                                ):
                                    files.append(self._parse_file_metadata(file))
                        else:
                            files.extend(
                                [self._parse_file_metadata(file) for file in page_files]
                            )
                    except gitlab.exceptions.GitlabListError as err:
                        logger.warning(f"Failed to access resource, error={str(err)}")
                        return []
                    current_page_id += 1

            return await get_event_loop().run_in_executor(executor, fetch_func)
