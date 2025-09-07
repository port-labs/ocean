from typing import Any, Dict, List

from loguru import logger

from github.clients.rest_client import RestClient
from github.kind.object_kind import ObjectKind
from github.exporters.base import BaseExporter
from github.exporters.respository import RepositoryExporter


class IssueExporter(BaseExporter):
    """Exporter for GitHub Issues"""

    KIND = ObjectKind.ISSUE.value

    def __init__(self, repos: List[str] | None = None) -> None:
        self.client = RestClient()
        self._repos = repos or []
        

    async def export(self) -> List[Dict[str, Any]]:
        """
        Export issues from all repositories under the configured owner

        Returns:
            List of issue dicts as returned by GitHub API
        """
        try:
            logger.info(
                f"[{self.__class__.__name__}] kind={self.KIND} Starting export from GitHub API (all repos)"
            )
            owner = self.get_repo_owner()
            repositories = (
                [{"name": n} for n in self._repos]
                if self._repos
                else await RepositoryExporter().export()
            )

            all_issues: list[dict[str, Any]] = []
            for repo in repositories:
                repo_name = repo.get("name")
                if not repo_name:
                    continue
                response = await self.client.get(
                    f"/repos/{owner}/{repo_name}/issues",
                    params={"state": "all"},
                )
                logger.info(
                    f"[{self.__class__.__name__}] repo={repo_name} status={response.status_code}"
                )
                response.raise_for_status()
                issues = response.json()
                if isinstance(issues, list):
                    for item in issues:
                        if "pull_request" in item:
                            continue
                        # attach repository context for relations mapping
                        item.setdefault("__repository", repo_name)
                        all_issues.append(item)

            return all_issues

        except Exception as e:
            logger.error(
                f"[{self.__class__.__name__}] kind={self.KIND} Failed to export issues | error={e}",
                exc_info=True,
            )
            return []


