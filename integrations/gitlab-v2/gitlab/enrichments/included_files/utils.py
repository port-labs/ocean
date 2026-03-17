from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable, Optional

from port_ocean.core.utils.included_files import (
    repo_branch_matches,
    resolve_included_file_path,
)


@dataclass(frozen=True)
class IncludedFilesEntityContext:
    project_path: str
    project_id: str
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


__all__ = [
    "IncludedFilesEntityContext",
    "FolderIncludedFilesRequests",
    "IncludedFilesTarget",
    "IncludedFilesPlanItem",
    "unique_preserve_order",
    "repo_branch_matches",
    "resolve_included_file_path",
]
