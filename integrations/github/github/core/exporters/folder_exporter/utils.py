from datetime import datetime
from typing import Any, List, Optional
from github.core.options import (
    FolderSearchOptions,
    ListFolderOptions,
)
from github.helpers.pattern_mapping_builder import PatternMappingBuilder
from integration import FolderSelector


class FolderPatternMappingBuilder(
    PatternMappingBuilder[FolderSearchOptions, ListFolderOptions]
):
    selector_kind = "folder"

    def _search_options(
        self,
        selector: FolderSelector,
        org_login: str,
        branch: str,
        repo_obj: dict[str, Any],
    ) -> FolderSearchOptions:
        return FolderSearchOptions(
            organization=org_login,
            branch=branch,
            path=selector.path,
            repo=repo_obj,
        )

    def _list_options(
        self,
        org: str,
        repo: str,
        items: List[FolderSearchOptions],
        changed_since: Optional[datetime],
    ) -> ListFolderOptions:
        return ListFolderOptions(
            organization=org,
            repo_name=repo,
            folders=items,
            changed_since=changed_since,
        )
