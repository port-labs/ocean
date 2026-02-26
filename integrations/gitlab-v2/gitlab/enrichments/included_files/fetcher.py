import asyncio
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from gitlab.clients.gitlab_client import GitLabClient


@dataclass(frozen=True)
class IncludedFileFetchKey:
    project_path: str
    project_id: str
    branch: Optional[str]
    file_path: str


class IncludedFilesFetcher:
    """
    Fetches file contents with:

    - In-flight deduplication
    - Batch-scoped result caching
    - Concurrency handled by asyncio.gather
    """

    def __init__(self, *, client: GitLabClient) -> None:
        self._client = client
        self._results: dict[IncludedFileFetchKey, Optional[str]] = {}
        self._inflight: dict[IncludedFileFetchKey, asyncio.Task[Optional[str]]] = {}

    async def get(self, key: IncludedFileFetchKey) -> Optional[str]:
        if key in self._results:
            return self._results[key]

        task = self._inflight.get(key)
        if task is None:
            task = asyncio.create_task(self._fetch(key))
            self._inflight[key] = task

        try:
            result = await task
            self._results[key] = result
            return result
        finally:
            self._inflight.pop(key, None)

    async def _fetch(self, key: IncludedFileFetchKey) -> Optional[str]:
        if not key.project_path or not key.file_path:
            return None

        project_path = key.project_path
        branch = key.branch or "main"
        path = key.file_path

        try:
            content = await self._client.get_file_content(project_path, path, branch)

            if content:
                logger.info(
                    f"IncludedFilesFetcher: fetched file content "
                    f"(project={project_path}, branch={branch}, path={path})"
                )
            else:
                logger.info(
                    f"IncludedFilesFetcher: no content for file "
                    f"(project={project_path}, branch={branch}, path={path})"
                )

            return content
        except Exception as e:
            logger.debug(
                f"IncludedFilesFetcher: could not fetch file "
                f"(project={project_path}, branch={branch}, path={path}): {e}"
            )
            return None
