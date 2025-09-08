from typing import Any, Dict, List

from loguru import logger

from github.clients.rest_client import RestClient
from github.exporters.base import BaseExporter
from github.exporters.respository import RepositoryExporter
from github.kind.object_kind import ObjectKind
from github.settings import SETTINGS
from datetime import datetime, timedelta, timezone


class PullRequestExporter(BaseExporter):
    """Exporter for GitHub Pull Requests across all repositories."""

    KIND = ObjectKind.PULL_REQUEST.value

    def __init__(self, repos: List[str] | None = None) -> None:
        self.client = RestClient()
        self._repos = repos or []

    async def export(self) -> List[Dict[str, Any]]:
        try:
            logger.info(
                f"[{self.__class__.__name__}] kind={self.KIND} Starting export from GitHub API (all repos)"
            )
            owner = self.get_repo_owner()
            repositories = (
                [{"name": n} for n in self._repos] if self._repos else await RepositoryExporter().export()
            )

            params = self._build_query_params()
            updated_cutoff = self._compute_updated_cutoff()

            all_prs: list[dict[str, Any]] = []
            for repo in repositories:
                repo_name = repo.get("name")
                if not isinstance(repo_name, str) or not repo_name:
                    continue
                repo_prs = await self._fetch_repository_pull_requests(owner, repo_name, params)
                repo_prs = self._filter_by_updated_since(repo_prs, updated_cutoff)
                all_prs.extend(self._enrich_with_repository(repo_prs, repo_name))

            return all_prs
        except Exception as e:
            logger.error(
                f"[{self.__class__.__name__}] kind={self.KIND} Failed to export pull requests | error={e}",
                exc_info=True,
            )
            return []

    def _build_query_params(self) -> Dict[str, Any]:
        state = (SETTINGS.pr_state or "all").lower()
        return {"state": state, "per_page": 100}

    def _compute_updated_cutoff(self) -> datetime | None:
        raw_days = SETTINGS.pr_updated_since_days
        if not raw_days:
            return None
        try:
            days = int(raw_days)
            return datetime.now(timezone.utc) - timedelta(days=days)
        except Exception:
            return None

    async def _fetch_repository_pull_requests(
        self, owner: str, repo_name: str, params: Dict[str, Any]
    ) -> list[dict[str, Any]]:
        data = await self.client.get_paginated(
            f"/repos/{owner}/{repo_name}/pulls", params=params
        )
        return data if isinstance(data, list) else []

    def _filter_by_updated_since(
        self, prs: list[dict[str, Any]], updated_cutoff: datetime | None
    ) -> list[dict[str, Any]]:
        if not updated_cutoff:
            return prs
        filtered: list[dict[str, Any]] = []
        for pr in prs:
            try:
                updated_str = pr.get("updated_at")
                if not updated_str:
                    continue
                updated_dt = datetime.strptime(updated_str, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
                if updated_dt >= updated_cutoff:
                    filtered.append(pr)
            except Exception:
                # If parsing fails, skip the item to avoid stale data
                continue
        return filtered

    def _enrich_with_repository(
        self, prs: list[dict[str, Any]], repo_name: str
    ) -> list[dict[str, Any]]:
        for pr in prs:
            pr.setdefault("__repository", repo_name)
        return prs


