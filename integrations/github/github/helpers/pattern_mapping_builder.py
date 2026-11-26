from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.options import ListOrganizationOptions
from github.helpers.repo_selectors import CompositeRepositorySelector


class PatternMappingBuilder[SearchOptionsT, ListOptionsT](ABC):
    """Group path selectors (files, folders) per repository.

    Subclasses only say how one matched repository becomes search options and
    how a repository's options are wrapped into the list options.
    """

    selector_kind: str

    def __init__(
        self,
        org_exporter: AbstractGithubExporter[Any],
        repo_exporter: AbstractGithubExporter[Any],
        repo_type: str,
    ):
        self.org_exporter = org_exporter
        self.repo_selector = CompositeRepositorySelector(repo_type)
        self.repo_exporter = repo_exporter

    @abstractmethod
    def _search_options(
        self,
        selector: Any,
        org_login: str,
        branch: str,
        repo_obj: dict[str, Any],
    ) -> SearchOptionsT: ...

    @abstractmethod
    def _list_options(
        self,
        org: str,
        repo: str,
        items: List[SearchOptionsT],
        changed_since: Optional[datetime],
    ) -> ListOptionsT: ...

    async def build(
        self,
        selectors: List[Any],
        changed_since: Optional[datetime] = None,
    ) -> List[ListOptionsT]:
        """Group selectors per repository.

        With ``changed_since``, only repositories pushed since then are kept, and
        each is limited to what changed since then.
        """
        repo_map: Dict[Tuple[str, str], List[SearchOptionsT]] = defaultdict(list)

        logger.info(
            f"Building path mapping for {len(selectors)} {self.selector_kind} selectors..."
        )

        for selector in selectors:
            async for batch in self.org_exporter.get_paginated_resources(
                ListOrganizationOptions(organization=selector.organization)
            ):
                for org in batch:
                    org_login = org["login"]
                    org_type = org["type"]
                    async for (
                        repo_name,
                        branch,
                        repo_obj,
                    ) in self.repo_selector.select_repos(
                        selector,
                        self.repo_exporter,
                        org_login,
                        org_type,
                        pushed_since=changed_since,
                    ):
                        repo_map[(org_login, repo_name)].append(
                            self._search_options(selector, org_login, branch, repo_obj)
                        )

        return [
            self._list_options(org, repo, items, changed_since)
            for (org, repo), items in repo_map.items()
        ]
