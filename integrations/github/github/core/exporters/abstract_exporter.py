from abc import ABC, abstractmethod
from typing import Any, Optional
from datetime import datetime
from loguru import logger
from github.clients.http.base_client import AbstractGithubClient
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class AbstractGithubExporter[T: AbstractGithubClient](ABC):
    def __init__(self, client: T) -> None:
        self.client = client

    @abstractmethod
    async def get_resource[AnyOption: Any](
        self, options: AnyOption
    ) -> Optional[RAW_ITEM]: ...

    @abstractmethod
    def get_paginated_resources[AnyOption: Any](
        self, options: AnyOption
    ) -> ASYNC_GENERATOR_RESYNC_TYPE: ...

    async def has_path_changes_since(
        self, organization: str, repo_name: str, path: str, cursor: datetime | None
    ) -> bool:
        """Check if repo has commits touching path since cursor."""
        if not cursor:
            logger.info(
                f"[file-incremental] {organization}/{repo_name}: no cursor provided, "
                f"treating path={path!r} as changed"
            )
            return True

        since_date = cursor.isoformat()
        url = f"{self.client.base_url}/repos/{organization}/{repo_name}/commits"
        params = {"path": path, "since": since_date, "per_page": 1}
        logger.info(
            f"[file-incremental] Checking path changes for {organization}/{repo_name}: "
            f"GET {url} params={params} cursor={since_date}"
        )

        async for commits_page in self.client.send_paginated_request(url, params):
            commits = (
                commits_page
                if isinstance(commits_page, list)
                else commits_page.get("items", [])
            )
            if commits:
                sample = commits[0]
                commit_meta = (
                    sample.get("commit", {}) if isinstance(sample, dict) else {}
                )
                logger.info(
                    f"[file-incremental] {organization}/{repo_name}: path={path!r} "
                    f"HAS changes since cursor={since_date} "
                    f"commits_returned={len(commits)} "
                    f"latest_sha={sample.get('sha') if isinstance(sample, dict) else None} "
                    f"latest_date={commit_meta.get('author', {}).get('date') or commit_meta.get('committer', {}).get('date')} "
                    f"latest_message={(commit_meta.get('message') or '')[:120]!r}"
                )
                return True

            logger.info(
                f"[file-incremental] {organization}/{repo_name}: path={path!r} "
                f"NO changes since cursor={since_date} (empty commits page)"
            )
            return False

        logger.info(
            f"[file-incremental] {organization}/{repo_name}: path={path!r} "
            f"NO changes since cursor={since_date} (no commits pages returned)"
        )
        return False
