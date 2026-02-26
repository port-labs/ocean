import fnmatch
from pathlib import PurePosixPath
from typing import Any, Protocol, Sequence

from integration import FolderPattern

from gitlab.enrichments.included_files.utils import (
    FolderIncludedFilesRequests,
    IncludedFilesEntityContext,
    IncludedFilesPlanItem,
    IncludedFilesTarget,
    repo_branch_matches,
    unique_preserve_order,
)


class IncludedFilesStrategy(Protocol):
    def context_for(self, entity: dict[str, Any]) -> IncludedFilesEntityContext: ...

    def requested_paths_for(self, entity: dict[str, Any]) -> list[str]: ...

    def plan_items_for(
        self, entity: dict[str, Any], ctx: IncludedFilesEntityContext
    ) -> list[IncludedFilesPlanItem]: ...


class ProjectIncludedFilesStrategy:
    def __init__(self, *, included_files: Sequence[str]) -> None:
        self._included_files = list(included_files)

    def context_for(self, entity: dict[str, Any]) -> IncludedFilesEntityContext:
        project_path = entity.get("path_with_namespace", str(entity.get("id", "")))
        project_id = str(entity.get("id", ""))
        branch = entity.get("default_branch", "main")
        return IncludedFilesEntityContext(
            project_path=project_path,
            project_id=project_id,
            branch=branch,
            base_path="",
        )

    def requested_paths_for(self, entity: dict[str, Any]) -> list[str]:
        return list(self._included_files)

    def plan_items_for(
        self, entity: dict[str, Any], ctx: IncludedFilesEntityContext
    ) -> list[IncludedFilesPlanItem]:
        return [
            IncludedFilesPlanItem(
                target=IncludedFilesTarget.ENTITY,
                requested_path=requested,
                base_path="",
            )
            for requested in self.requested_paths_for(entity)
        ]


class FolderIncludedFilesStrategy:
    def __init__(
        self,
        *,
        folder_selectors: Sequence[FolderPattern],
        global_included_files: Sequence[str] = (),
    ) -> None:
        self._selectors = list(folder_selectors)
        self._global_included_files = list(global_included_files)

    def context_for(self, entity: dict[str, Any]) -> IncludedFilesEntityContext:
        project = entity.get("__project") or entity.get("repo", {})
        project_path = project.get("path_with_namespace") or str(project.get("id", ""))
        project_id = str(project.get("id", ""))
        branch = entity.get("branch") or project.get("default_branch", "main")
        folder_path = entity.get("path", "")
        return IncludedFilesEntityContext(
            project_path=project_path,
            project_id=project_id,
            branch=branch,
            base_path=folder_path,
        )

    def requested_paths_for(self, entity: dict[str, Any]) -> list[str]:
        included_files_requests = self.resolve_included_files_for(entity)
        return (
            included_files_requests.global_paths + included_files_requests.folder_paths
        )

    def plan_items_for(
        self, entity: dict[str, Any], ctx: IncludedFilesEntityContext
    ) -> list[IncludedFilesPlanItem]:
        included_files_requests = self.resolve_included_files_for(entity)

        global_items = [
            IncludedFilesPlanItem(
                target=IncludedFilesTarget.ENTITY,
                requested_path=requested,
                base_path="",
            )
            for requested in included_files_requests.global_paths
        ]
        folder_items = [
            IncludedFilesPlanItem(
                target=IncludedFilesTarget.FOLDER,
                requested_path=requested,
                base_path=ctx.base_path,
            )
            for requested in included_files_requests.folder_paths
        ]
        return global_items + folder_items

    def resolve_included_files_for(
        self, entity: dict[str, Any]
    ) -> FolderIncludedFilesRequests:
        ctx = self.context_for(entity)
        project = entity.get("__project") or entity.get("repo", {})
        default_branch = project.get("default_branch", "main")
        folder_path = entity.get("path", "")
        project_path = project.get("path_with_namespace", "")

        global_paths = unique_preserve_order(self._global_included_files)
        folder_paths: list[str] = []
        for selector in self._selectors:
            if not repo_branch_matches(
                repos=selector.repos,
                repo_name=project_path,
                branch=ctx.branch,
                default_branch=default_branch,
            ):
                continue

            if not fnmatch.fnmatch(folder_path, selector.path):
                continue

            # FolderPattern doesn't have included_files - they come from global_included_files

        return FolderIncludedFilesRequests(
            global_paths=global_paths,
            folder_paths=unique_preserve_order(folder_paths),
        )


class FileIncludedFilesStrategy:
    def __init__(
        self,
        *,
        included_files: Sequence[str],
    ) -> None:
        self._included_files = list(included_files)

    def context_for(self, entity: dict[str, Any]) -> IncludedFilesEntityContext:
        # Project can be in entity["repo"], entity["__project"], or entity["project"]
        project = entity.get("repo", {}) or entity.get("__project", {}) or entity.get("project", {})
        project_path = project.get("path_with_namespace") or str(project.get("id", ""))
        project_id = str(project.get("id", ""))
        branch = entity.get("branch") or project.get("default_branch", "main")
        # File path can be in entity["file"]["path"] or entity["path"]
        file_path = entity.get("file", {}).get("path", "") or entity.get("path", "")
        if file_path:
            base_path = str(PurePosixPath(file_path).parent)
            # Treat "." as empty base path
            if base_path == ".":
                base_path = ""
        else:
            base_path = ""
        return IncludedFilesEntityContext(
            project_path=project_path,
            project_id=project_id,
            branch=branch,
            base_path=base_path,
        )

    def requested_paths_for(self, entity: dict[str, Any]) -> list[str]:
        return list(self._included_files)

    def plan_items_for(
        self, entity: dict[str, Any], ctx: IncludedFilesEntityContext
    ) -> list[IncludedFilesPlanItem]:
        return [
            IncludedFilesPlanItem(
                target=IncludedFilesTarget.ENTITY,
                requested_path=requested,
                base_path=ctx.base_path,
            )
            for requested in self.requested_paths_for(entity)
        ]
