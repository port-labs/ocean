"""Utilities for resolving included-files paths and repo/branch matching."""

import posixpath
from typing import Optional, Protocol, Sequence


class RepoBranchMappingLike(Protocol):
    """Protocol for repo/branch mapping (e.g. selector.repos items)."""

    name: str
    branch: Optional[str]


def repo_branch_matches(
    *,
    repos: Optional[Sequence[RepoBranchMappingLike]],
    repo_name: str,
    branch: Optional[str],
    default_branch: Optional[str],
) -> bool:
    """
    Return True if the given repo/branch is allowed by the repos mapping.

    - When repos is None or empty, returns True only for the default branch.
    - When repos is set, returns True if repo_name matches a mapping and either:
      - mapping.branch is "default" and branch is the default branch, or
      - mapping.branch equals branch, or
      - mapping.branch is None and branch is the default branch.
    """
    is_default = branch is not None and branch == default_branch

    if not repos:
        return is_default

    for mapping in repos:
        if mapping.name != repo_name:
            continue

        if mapping.branch == "default":
            if is_default:
                return True
        elif mapping.branch is not None:
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
    - Treat "." as empty base path.
    """
    if not requested_path:
        return requested_path

    clean_requested = requested_path.lstrip("/")
    clean_base = (base_path or "").strip("/")

    # Treat "." as empty base path
    if clean_base == ".":
        clean_base = ""

    if not clean_base:
        return clean_requested

    if clean_requested.startswith(f"{clean_base}/"):
        return clean_requested

    return posixpath.join(clean_base, clean_requested)
