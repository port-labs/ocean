from collections import defaultdict
from typing import Any, Dict, List, Tuple
from loguru import logger
from github.clients.utils import get_mono_repo_organization
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import FolderSearchOptions, ListFolderOptions
from github.helpers.repo_selectors import (
    CompositeRepositorySelector,
    OrganizationLoginGenerator,
)
from integration import FolderSelector


class FolderPatternMappingBuilder:
    def __init__(
        self,
        org_exporter: AbstractGithubExporter[Any],
        repo_exporter: AbstractGithubExporter[Any],
        repo_type: str,
    ):
        self.generate_org_logins = OrganizationLoginGenerator(org_exporter)
        self.repo_selector = CompositeRepositorySelector(repo_type)
        self.repo_exporter = repo_exporter

    async def build(self, folders: List[FolderSelector]) -> List[ListFolderOptions]:
        repo_map: Dict[Tuple[str, str], List[FolderSearchOptions]] = defaultdict(list)

        logger.info(f"Building path mapping for {len(folders)} folder selectors...")

        for folder_sel in folders:
            organization = get_mono_repo_organization(folder_sel.organization)
            async for org_login in self.generate_org_logins(organization):
                async for (
                    repo_name,
                    branch,
                    repo_obj,
                ) in self.repo_selector.select_repos(
                    folder_sel, self.repo_exporter, org_login
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
