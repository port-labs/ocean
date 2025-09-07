from typing import Any, Dict, List

from loguru import logger

from github.clients.rest_client import RestClient
from github.exporters.base import BaseExporter
from github.exporters.respository import RepositoryExporter
from github.kind.object_kind import ObjectKind


class PullRequestExporter(BaseExporter):
    """Exporter for GitHub Pull Requests across all repositories."""

    KIND = ObjectKind.PULL_REQUEST.value

    def __init__(self, repos: List[str] | None = None) -> None:
        self.client = RestClient()
        self._repos = repos or []

    async def export(self) -> List[Dict[str, Any]]:
        try:
            logger.info(f"[{self.__class__.__name__}] kind={self.KIND} Starting export from GitHub API (all repos)")
            owner = self.get_repo_owner()
            repositories = (
                [{"name": n} for n in self._repos]
                if self._repos
                else await RepositoryExporter().export()
            )

            all_prs: list[dict[str, Any]] = []
            for repo in repositories:
                repo_name = repo.get("name")
                if not repo_name:
                    continue
                resp = await self.client.get(
                    f"/repos/{owner}/{repo_name}/pulls", params={"state": "all"}
                )
                logger.info(f"[{self.__class__.__name__}] repo={repo_name} status={resp.status_code}")
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    for pr in data:
                        pr.setdefault("__repository", repo_name)
                        all_prs.append(pr)

            return all_prs
        except Exception as e:
            logger.error(
                f"[{self.__class__.__name__}] kind={self.KIND} Failed to export pull requests | error={e}",
                exc_info=True,
            )
            return []


