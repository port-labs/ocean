from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import (
    FolderSearchOptions,
    ListOrganizationOptions,
    ListFolderOptions,
)
from github.helpers.repo_selectors import CompositeRepositorySelector
from integration import FolderSelector


class FolderPatternMappingBuilder:
    def __init__(
        self,
        org_exporter: AbstractGithubExporter[Any],
        repo_exporter: AbstractGithubExporter[Any],
        repo_type: str,
    ):
        self.org_exporter = org_exporter
        self.repo_exporter = repo_exporter
        self.repo_type = repo_type

    async def build(
        self,
        folders: List[FolderSelector],
        updated_since: Optional[datetime] = None,
        cursor_field: str = "updated_at",
    ) -> List[ListFolderOptions]:
        """Build folder search options from patterns.
        Supports both incremental and full sync modes:
        - If updated_since is provided (incremental): only repos modified since timestamp
        - If updated_since is None (full sync): all repos

        Args:
            folders: Folder patterns to match against repositories
            updated_since: Optional cursor for incremental sync
            cursor_field: Which field to use for filtering ("updated_at" or "pushed_at")
        """
        repo_map: Dict[Tuple[str, str], List[FolderSearchOptions]] = defaultdict(list)

        logger.info(f"Building path mapping for {len(folders)} folder selectors...")

        repo_selector = CompositeRepositorySelector(
            self.repo_type, updated_since=updated_since, cursor_field=cursor_field
        )

        for folder_sel in folders:
            async for batch in self.org_exporter.get_paginated_resources(
                ListOrganizationOptions(organization=folder_sel.organization)
            ):
                for org in batch:
                    org_login = org["login"]
                    org_type = org["type"]
                    async for (
                        repo_name,
                        branch,
                        repo_obj,
                    ) in repo_selector.select_repos(
                        folder_sel, self.repo_exporter, org_login, org_type
                    ):
                        key = (org_login, repo_name)
                        repo_map[key].append(
                            FolderSearchOptions(
                                organization=org_login,
                                branch=branch,
                                path=folder_sel.path,
                                repo=repo_obj,
                            )
                        )

        return [
            ListFolderOptions(
                organization=org,
                repo_name=repo,
                folders=items,
            )
            for (org, repo), items in repo_map.items()
        ]
