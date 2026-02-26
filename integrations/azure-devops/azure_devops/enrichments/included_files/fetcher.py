import asyncio
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from azure_devops.client.azure_devops_client import AzureDevopsClient


@dataclass(frozen=True)
class IncludedFileFetchKey:
    project_id: str
    repo_id: str
    repo_name: str
    branch: Optional[str]
    file_path: str


class IncludedFilesFetcher:
    """
    Fetches file contents with:

    - In-flight deduplication
    - Batch-scoped result caching
    - Concurrency handled by asyncio.gather
    """

    def __init__(self, *, client: AzureDevopsClient) -> None:
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
        if not key.repo_id or not key.file_path:
            return None

        repo_id = key.repo_id
        branch = key.branch
        path = key.file_path

        try:
            content_bytes = await self._client.get_file_by_branch(
                path, repo_id, branch or "main"
            )
            # Handle empty bytes - return empty string, not None
            if content_bytes is None:
                content = None
            else:
                content = content_bytes.decode("utf-8") if content_bytes else ""

            if content is not None:
                logger.info(
                    f"IncludedFilesFetcher: fetched file content "
                    f"(repo={key.repo_name}, branch={branch}, path={path})"
                )
            else:
                logger.info(
                    f"IncludedFilesFetcher: no content for file "
                    f"(repo={key.repo_name}, branch={branch}, path={path})"
                )

            return content
        except Exception as e:
            logger.debug(
                f"IncludedFilesFetcher: could not fetch file "
                f"(repo={key.repo_name}, branch={branch}, path={path}): {e}"
            )
            return None
