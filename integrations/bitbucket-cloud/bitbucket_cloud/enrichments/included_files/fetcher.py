import asyncio
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from bitbucket_cloud.client import BitbucketClient


@dataclass(frozen=True)
class IncludedFileFetchKey:
    workspace: str
    repo_slug: str
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

    def __init__(self, *, client: BitbucketClient) -> None:
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
        if not key.repo_slug or not key.file_path:
            return None

        repo_slug = key.repo_slug
        branch = key.branch or "main"
        path = key.file_path

        try:
            content = await self._client.get_repository_files(repo_slug, branch, path)

            if content:
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
