"""Utilities for resolving included-files paths in repo-relative form."""

import posixpath


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
