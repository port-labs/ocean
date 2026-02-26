import fnmatch
from pathlib import PurePosixPath
from typing import Any, Protocol, Sequence

from azure_devops.misc import AzureDevopsFolderSelector

from azure_devops.enrichments.included_files.utils import (
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


class RepositoryIncludedFilesStrategy:
    def __init__(self, *, included_files: Sequence[str]) -> None:
        self._included_files = list(included_files)

    def context_for(self, entity: dict[str, Any]) -> IncludedFilesEntityContext:
        project = entity.get("project", {})
        project_id = project.get("id", "")
        repo_id = entity.get("id", "")
        repo_name = entity.get("name", "")
        default_branch_ref = entity.get("defaultBranch", "refs/heads/main")
        branch = default_branch_ref.replace("refs/heads/", "")
        return IncludedFilesEntityContext(
            project_id=project_id,
            repo_id=repo_id,
            repo_name=repo_name,
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
        folder_selectors: Sequence[AzureDevopsFolderSelector],
        global_included_files: Sequence[str] = (),
    ) -> None:
        self._selectors = list(folder_selectors)
        self._global_included_files = list(global_included_files)

    def context_for(self, entity: dict[str, Any]) -> IncludedFilesEntityContext:
        repo = entity.get("__repository", {})
        project = repo.get("project", {})
        project_id = project.get("id", "")
        repo_id = repo.get("id", "")
        repo_name = repo.get("name", "")
        branch = entity.get("__branch") or repo.get(
            "defaultBranch", "refs/heads/main"
        ).replace("refs/heads/", "")
        folder_path = entity.get("path", "")
        return IncludedFilesEntityContext(
            project_id=project_id,
            repo_id=repo_id,
            repo_name=repo_name,
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
        repo = entity.get("__repository") or {}
        default_branch_ref = repo.get("defaultBranch", "refs/heads/main")
        default_branch = default_branch_ref.replace("refs/heads/", "")
        folder_path = entity.get("path", "")

        global_paths = unique_preserve_order(self._global_included_files)
        folder_paths: list[str] = []
        for selector in self._selectors:
            if not repo_branch_matches(
                repos=selector.repos,
                repo_name=ctx.repo_name,
                branch=ctx.branch,
                default_branch=default_branch,
            ):
                continue

            if not fnmatch(folder_path, selector.path):
                continue

            folder_paths.extend(selector.included_files or [])

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
        repo = entity.get("repo", {})
        project = repo.get("project", {})
        project_id = project.get("id", "")
        repo_id = repo.get("id", "")
        repo_name = repo.get("name", "")
        branch_ref = entity.get("branch") or repo.get(
            "defaultBranch", "refs/heads/main"
        )
        branch = branch_ref.replace("refs/heads/", "") if isinstance(branch_ref, str) else branch_ref
        file_path = entity.get("path", "")
        base_path = str(PurePosixPath(file_path).parent)
        return IncludedFilesEntityContext(
            project_id=project_id,
            repo_id=repo_id,
            repo_name=repo_name,
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
