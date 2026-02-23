import asyncio
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.options import FileContentOptions


@dataclass(frozen=True)
class IncludedFileFetchKey:
    organization: str
    repo_name: str
    branch: Optional[str]
    file_path: str


class IncludedFilesFetcher:
    """
    Fetches file contents with:

    - In-flight deduplication
    - Batch-scoped result caching
    - Concurrency handled by RestFileExporter rate limiter
    """

    def __init__(self, *, rest_client: Any) -> None:
        self._exporter = RestFileExporter(rest_client)
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
        if not key.organization or not key.repo_name or not key.file_path:
            return None

        org = key.organization
        repo = key.repo_name
        branch = key.branch
        path = key.file_path

        response = await self._exporter.get_resource(
            FileContentOptions(
                organization=org, repo_name=repo, file_path=path, branch=branch
            )
        )

        if not response:
            logger.info(
                f"IncludedFilesFetcher: no response for file content "
                f"(org={org}, repo={repo}, branch={branch}, path={path})"
            )
            return None

        logger.info(
            f"IncludedFilesFetcher: fetched file content "
            f"(org={org}, repo={repo}, branch={branch}, path={path})"
        )

        return response.get("content")
