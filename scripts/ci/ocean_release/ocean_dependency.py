"""Validate that every integration pins port_ocean to the core version."""

from __future__ import annotations

from utils import list_integrations

from .git_context import GitContext
from .version import parse_port_ocean_dependency_version, parse_version


def validate_ocean_dependency_bumps(git: GitContext) -> list[str]:
    """Ensure every integration's ``port_ocean`` matches core's version."""
    try:
        core_version = parse_version(
            git.read_worktree(git.repo_root / "pyproject.toml")
        )
    except (OSError, ValueError) as exc:
        return [f"ocean-core: could not read version from pyproject.toml ({exc})"]

    integrations = list_integrations(git.repo_root)
    print(
        f"Checking {len(integrations)} integration(s) pin port_ocean to "
        f"^{core_version}"
    )

    outdated: list[str] = []
    for name in integrations:
        pyproject = git.repo_root / "integrations" / name / "pyproject.toml"
        head_version = parse_port_ocean_dependency_version(git.read_worktree(pyproject))
        if head_version is None:
            raise ValueError(
                f"{name}: port_ocean dependency version is required in pyproject.toml"
            )
        if head_version.lstrip("^") != core_version:
            outdated.append(f"{name}={head_version}")

    if not outdated:
        print(f"All integrations pin port_ocean to ^{core_version}")
        return []

    return [
        "Every integration must pin port_ocean to the core version "
        f"^{core_version}; outdated: {', '.join(outdated)}"
    ]
