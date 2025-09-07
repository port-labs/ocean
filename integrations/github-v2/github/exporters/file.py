from __future__ import annotations

from typing import Any

from loguru import logger

from github.clients.rest_client import RestClient
from github.exporters.base import BaseExporter
from github.exporters.respository import RepositoryExporter
from github.kind.object_kind import ObjectKind
from github.settings import SETTINGS


class FileExporter(BaseExporter):
    """Exporter for GitHub Files"""

    KIND = ObjectKind.FILE.value

    def __init__(self, repos: list[str] | None = None, path: str | None = "") -> None:
        self.client = RestClient()
        self._repos = repos or []
        self.path = path or ""

    async def export(self) -> list[dict[str, Any]]:
        """
        Export files (or directories) from all repositories for the configured owner

        Returns:
            List of file dicts with metadata and decoded content
        """
        try:
            logger.info(
                f"[{self.__class__.__name__}] kind={self.KIND} Starting export from GitHub API"
            )

            owner = self.get_repo_owner()
            repositories = (
                [{"name": n} for n in self._repos]
                if self._repos
                else await RepositoryExporter().export()
            )

            all_files: list[dict[str, Any]] = []
            for repo in repositories:
                repo_name = repo.get("name")
                if not repo_name:
                    continue
                logger.info(f"[{self.__class__.__name__}] fetching files for repo={repo_name} path='{self.path or '/'}'")
                segment = "contents" if not self.path else f"contents/{self.path}"
                response = await self.client.get(f"/repos/{owner}/{repo_name}/{segment}")
                logger.info(
                    f"[{self.__class__.__name__}] repo={repo_name} status={response.status_code}"
                )
                if response.status_code == 404:
                    logger.warning(
                        f"[{self.__class__.__name__}] repo={repo_name} path={segment} not found (404), skipping"
                    )
                    continue

                data = response.json()

                if isinstance(data, dict):
                    file_item = self._process_file(data)
                    file_item.setdefault("repository", {"name": repo_name})
                    all_files.append(file_item)
                elif isinstance(data, list):
                    for item in data:
                        if item.get("type") != "file":
                            continue
                        file_item = self._process_file(item)
                        file_item.setdefault("repository", {"name": repo_name})
                        all_files.append(file_item)

            return all_files

        except Exception as e:
            logger.error(
                f"[{self.__class__.__name__}] kind={self.KIND} Failed to export files | error={e}",
                exc_info=True,
            )
            return []

    def _process_file(self, file_data: dict[str, Any]) -> dict[str, Any]:
        """Normalize GitHub file response."""
        return {
            "name": file_data.get("name"),
            "path": file_data.get("path"),
            "sha": file_data.get("sha"),
            "download_url": file_data.get("download_url"),
            "content": file_data.get("content"),  # Base64 encoded if file
            "encoding": file_data.get("encoding", "base64"),
        }


