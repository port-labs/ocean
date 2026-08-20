"""Release intent file parsing and discovery."""

from __future__ import annotations

from pathlib import Path

from .models import ReleaseIntent, ReleaseTarget
from .version import CHANGELOG_SECTIONS


def parse_release_yaml(content: str) -> dict[str, str]:
    data: dict[str, str] = {}
    current_key: str = ""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            if current_key != "changelog":
                raise ValueError(f"Invalid release file line: {line}")
            data[current_key] += f"\n{stripped}"
            continue
        key, value = stripped.split(":", 1)
        current_key = key.strip()
        data[current_key] = value.strip().strip('"').strip("'")
    return data


def parse_release_file(path: Path, content: str) -> ReleaseIntent:
    raw = parse_release_yaml(content)
    bump = raw.get("bump", "").lower()
    changelog_type = raw.get("changelog-type", raw.get("changelog_type", "")).lower()
    changelog = raw.get("changelog", "").strip()
    if bump not in {"patch", "minor", "major"}:
        raise ValueError(f"{path}: bump must be patch, minor, or major")
    if changelog_type not in CHANGELOG_SECTIONS:
        allowed = ", ".join(sorted(CHANGELOG_SECTIONS))
        raise ValueError(
            f"{path}: invalid changelog-type '{changelog_type}' (allowed: {allowed})"
        )
    if not changelog:
        raise ValueError(f"{path}: changelog is required")
    return ReleaseIntent(
        path=path,
        bump=bump,
        changelog_type=changelog_type,
        changelog=changelog,
    )


def target_from_release_path(repo_root: Path, relative_path: str) -> ReleaseTarget:
    parts = Path(relative_path).parts
    if parts[0] == "integrations":
        integration_name = parts[1]
        return ReleaseTarget(
            kind="integration",
            name=integration_name,
            pyproject_path=Path(
                repo_root, "integrations", integration_name, "pyproject.toml"
            ),
            changelog_path=Path(
                repo_root, "integrations", integration_name, "CHANGELOG.md"
            ),
        )
    if parts[0] == ".ocean-release":
        return ReleaseTarget(
            kind="core",
            name="core",
            pyproject_path=Path(repo_root, "pyproject.toml"),
            changelog_path=Path(repo_root, "CHANGELOG.md"),
        )
    raise ValueError(f"Unsupported release file path: {relative_path}")
