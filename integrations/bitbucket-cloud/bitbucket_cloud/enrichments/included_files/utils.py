from dataclasses import dataclass
from enum import StrEnum
import posixpath
from typing import Iterable, Optional, Sequence

from integration import RepositoryBranchMapping


@dataclass(frozen=True)
class IncludedFilesEntityContext:
    workspace: str
    repo_slug: str
    repo_name: str
    branch: Optional[str]
    base_path: str


@dataclass(frozen=True)
class FolderIncludedFilesRequests:
    """Represents includedFiles requests split by origin.

    - global_paths: from kind-level selector.includedFiles
    - folder_paths: from matched FolderSelector.includedFiles
    """

    global_paths: list[str]
    folder_paths: list[str]


class IncludedFilesTarget(StrEnum):
    ENTITY = "."
    FOLDER = "folder"


@dataclass(frozen=True)
class IncludedFilesPlanItem:
    """A single includedFiles enrichment operation for one entity."""

    target: IncludedFilesTarget
    requested_path: str
    base_path: str


def unique_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def repo_branch_matches(
    *,
    repos: Optional[Sequence[RepositoryBranchMapping]],
    repo_name: str,
    branch: Optional[str],
    default_branch: Optional[str],
) -> bool:
    is_default = branch is not None and branch == default_branch

    if not repos:
        return is_default

    for mapping in repos:
        if mapping.name != repo_name:
            continue

        if mapping.branch is not None:
            if branch == mapping.branch:
                return True
        else:
            if is_default:
                return True

    return False


def resolve_included_file_path(requested_path: str, base_path: str) -> str:
    """
    Resolve a configured includedFiles path into a repo-relative file path.

    Rules:
    - Leading '/' does not force repo-root if base_path is set.
    - All paths are ultimately repo-relative.
    - Prevent double-joining when requested already includes base_path.
    """

    if not requested_path:
        return requested_path

    clean_requested = requested_path.lstrip("/")
    clean_base = (base_path or "").strip("/")

    if not clean_base:
        return clean_requested

    if clean_requested.startswith(f"{clean_base}/"):
        return clean_requested

    return posixpath.join(clean_base, clean_requested)
