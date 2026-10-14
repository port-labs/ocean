from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Tuple
from loguru import logger
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import (
    FolderSearchOptions,
    ListOrganizationOptions,
    ListFolderOptions,
)
from github.helpers.repo_selectors import (
    CompositeRepositorySelector,
    MemoizedRepositorySelector,
)
from integration import FolderSelector


class FolderPatternMappingBuilder:
    def __init__(
        self,
        org_exporter: AbstractGithubExporter[Any],
        repo_exporter: AbstractGithubExporter[Any],
        repo_type: str,
    ):
        self.org_exporter = org_exporter
        self.repo_selector = CompositeRepositorySelector(repo_type)
        self.repo_exporter = repo_exporter

    async def build(
        self,
        folders: List[FolderSelector],
        updated_since: datetime | None = None,
    ) -> List[ListFolderOptions]:
        """Map each repo to its folder patterns; with ``updated_since`` only repos pushed since then."""
        repo_map: Dict[Tuple[str, str], List[FolderSearchOptions]] = defaultdict(list)
        repo_selector = MemoizedRepositorySelector(self.repo_selector)

        logger.info(f"Building path mapping for {len(folders)} folder selectors...")

        for folder_sel in folders:
            async for batch in self.org_exporter.get_paginated_resources(
                ListOrganizationOptions(organization=folder_sel.organization)
            ):
                for org in batch:
                    org_login = org["login"]
                    repos = await repo_selector.select_repos(
                        folder_sel,
                        self.repo_exporter,
                        org_login,
                        org["type"],
                        pushed_since=updated_since,
                    )
                    for repo_name, branch, repo_obj in repos:
                        key = (org_login, repo_name)
                        repo_map[key].append(
                            FolderSearchOptions(
                                organization=org_login,
                                branch=branch,
                                path=folder_sel.path,
                                repo=repo_obj,
                            )
                        )

        search_options = [
            ListFolderOptions(
                organization=org,
                repo_name=repo,
                folders=items,
            )
            for (org, repo), items in repo_map.items()
        ]
        if updated_since:
            for option in search_options:
                option["updated_since"] = updated_since
        return search_options
