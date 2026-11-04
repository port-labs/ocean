"""Tests for port_ocean pinning to the core Ocean version."""

from __future__ import annotations

from pathlib import Path

import pytest

from ocean_release.git_context import GitContext
from ocean_release.ocean_dependency import validate_ocean_dependency_bumps
from ocean_release.version import parse_port_ocean_dependency_version


class FakeGit(GitContext):
    def __init__(
        self,
        *,
        repo_root: Path,
        worktree: dict[str, str] | None = None,
    ) -> None:
        super().__init__(repo_root)
        self._worktree = worktree or {}

    def read_worktree(self, path: Path) -> str:
        rel = path.relative_to(self.repo_root).as_posix()
        if rel in self._worktree:
            return self._worktree[rel]
        return path.read_text(encoding="utf-8")


def _core_pyproject(version: str) -> str:
    return f'name = "port-ocean"\nversion = "{version}"\n'


def _pyproject(port_ocean_version: str) -> str:
    return (
        'name = "demo"\n'
        'version = "1.0.0"\n'
        f'port_ocean = {{version = "{port_ocean_version}", extras = ["cli"]}}\n'
    )


def _write_core(repo_root: Path, version: str = "0.57.0") -> None:
    (repo_root / "pyproject.toml").write_text(
        _core_pyproject(version), encoding="utf-8"
    )


def _write_integration(repo_root: Path, name: str, port_ocean_version: str) -> None:
    path = repo_root / "integrations" / name / "pyproject.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_pyproject(port_ocean_version), encoding="utf-8")


def test_parse_port_ocean_dependency_version_ignores_commented_override() -> None:
    content = (
        "# port_ocean = { path = '../../', develop = true, extras = ['all'] }\n"
        'port_ocean = {version = "^0.57.0", extras = ["cli"]}\n'
    )
    assert parse_port_ocean_dependency_version(content) == "^0.57.0"


def test_parse_port_ocean_dependency_version_missing() -> None:
    assert parse_port_ocean_dependency_version('version = "1.0.0"\n') is None


def test_all_on_latest_passes(tmp_path: Path) -> None:
    _write_core(tmp_path)
    _write_integration(tmp_path, "github", "^0.57.0")
    _write_integration(tmp_path, "jira", "^0.57.0")

    assert validate_ocean_dependency_bumps(FakeGit(repo_root=tmp_path)) == []


def test_outdated_integration_fails(tmp_path: Path) -> None:
    _write_core(tmp_path)
    _write_integration(tmp_path, "github", "^0.57.0")
    _write_integration(tmp_path, "jira", "^0.56.0")

    errors = validate_ocean_dependency_bumps(FakeGit(repo_root=tmp_path))
    assert len(errors) == 1
    assert "^0.57.0" in errors[0]
    assert "jira=^0.56.0" in errors[0]


def test_missing_port_ocean_raises(tmp_path: Path) -> None:
    _write_core(tmp_path)
    path = tmp_path / "integrations" / "github" / "pyproject.toml"
    path.parent.mkdir(parents=True)
    path.write_text('name = "demo"\nversion = "1.0.0"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="port_ocean dependency version is required"):
        validate_ocean_dependency_bumps(FakeGit(repo_root=tmp_path))


def test_infra_directory_is_ignored(tmp_path: Path) -> None:
    _write_core(tmp_path)
    _write_integration(tmp_path, "github", "^0.57.0")
    _write_integration(tmp_path, "_infra", "^0.1.0")

    assert validate_ocean_dependency_bumps(FakeGit(repo_root=tmp_path)) == []


def test_missing_core_version_fails(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text('name = "port-ocean"\n', encoding="utf-8")
    _write_integration(tmp_path, "github", "^0.57.0")

    errors = validate_ocean_dependency_bumps(FakeGit(repo_root=tmp_path))
    assert len(errors) == 1
    assert "ocean-core" in errors[0]
