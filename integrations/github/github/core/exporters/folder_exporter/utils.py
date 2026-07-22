from collections import defaultdict
from typing import Dict, List, Tuple
from loguru import logger
from github.core.exporters.organization_exporter import RestOrganizationExporter
from github.core.exporters.repository_exporter import RestRepositoryExporter
from github.core.options import (
    FolderSearchOptions,
    ListFolderOptions,
)
from github.helpers.repo_selectors import CompositeRepositorySelector
from integration import FolderSelector


class FolderPatternMappingBuilder:
    def __init__(
        self,
        org_exporter: RestOrganizationExporter,
        repo_exporter: RestRepositoryExporter,
        repo_type: str,
    ):
        self.org_exporter = org_exporter
        self.repo_selector = CompositeRepositorySelector(repo_type)
        self.repo_exporter = repo_exporter

    async def build(self, folders: List[FolderSelector]) -> List[ListFolderOptions]:
        repo_map: Dict[Tuple[str, str], List[FolderSearchOptions]] = defaultdict(list)

        logger.info(f"Building path mapping for {len(folders)} folder selectors...")

        for folder_sel in folders:
            async for batch in self.org_exporter.get_paginated_resources():
                for org in batch:
                    org_login = org["login"]
                    if (
                        folder_sel.organization
                        and folder_sel.organization.casefold() != org_login.casefold()
                    ):
                        continue
                    org_type = org["type"]
                    async for (
                        repo_name,
                        branch,
                        repo_obj,
                    ) in self.repo_selector.select_repos(
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
