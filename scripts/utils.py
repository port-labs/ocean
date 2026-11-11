"""Shared helpers for Ocean repo scripts."""

from __future__ import annotations

from pathlib import Path


def list_integrations(repo_root: Path) -> list[str]:
    """Return sorted integration names under ``integrations/``.

    Skips ``_infra`` and any directory without a ``pyproject.toml``.
    """
    integrations_dir = repo_root / "integrations"
    if not integrations_dir.is_dir():
        return []
    return sorted(
        path.name
        for path in integrations_dir.iterdir()
        if path.is_dir()
        and path.name != "_infra"
        and (path / "pyproject.toml").exists()
    )
