"""Tests for Ocean release PR validation."""

from __future__ import annotations

from pathlib import Path

from ocean_release.git_context import GitContext
from ocean_release.models import ReleaseTarget
from ocean_release.validator import validate


class FakeGit(GitContext):
    def __init__(
        self,
        *,
        repo_root: Path,
        targets: list[ReleaseTarget],
        release_files: list[str] | None = None,
        version_changed: set[str] | None = None,
        changelog_changed: set[str] | None = None,
        worktree: dict[str, str] | None = None,
    ) -> None:
        super().__init__(repo_root)
        self._targets = targets
        self._release_files = release_files or []
        self._version_changed = version_changed or set()
        self._changelog_changed = changelog_changed or set()
        self._worktree = worktree or {}

    def changed_release_targets(
        self, base_ref: str, head_ref: str
    ) -> list[ReleaseTarget]:
        return list(self._targets)

    def release_files_added_in_diff(
        self, base_ref: str, head_ref: str | None = None
    ) -> list[str]:
        return list(self._release_files)

    def has_version_changed(
        self, base_ref: str, head_ref: str, pyproject: Path
    ) -> bool:
        return pyproject.relative_to(self.repo_root).as_posix() in self._version_changed

    def has_changelog_changed(
        self, base_ref: str, head_ref: str, changelog: Path
    ) -> bool:
        return (
            changelog.relative_to(self.repo_root).as_posix() in self._changelog_changed
        )

    def read_worktree(self, path: Path) -> str:
        rel = path.relative_to(self.repo_root).as_posix()
        if rel in self._worktree:
            return self._worktree[rel]
        return path.read_text(encoding="utf-8")


def _core_target(repo_root: Path) -> ReleaseTarget:
    return ReleaseTarget(
        kind="core",
        name="core",
        pyproject_path=repo_root / "pyproject.toml",
        changelog_path=repo_root / "CHANGELOG.md",
    )


def _integration_target(repo_root: Path, name: str) -> ReleaseTarget:
    return ReleaseTarget(
        kind="integration",
        name=name,
        pyproject_path=repo_root / "integrations" / name / "pyproject.toml",
        changelog_path=repo_root / "integrations" / name / "CHANGELOG.md",
    )


def _write_pyproject(path: Path, version: str = "0.1.0") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'name = "demo"\nversion = "{version}"\n', encoding="utf-8")


def _write_release(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "bump: patch\nchangelog-type: bugfix\nchangelog: Fixed something\n",
        encoding="utf-8",
    )


def test_core_intent_covers_changed_integration(tmp_path: Path) -> None:
    core = _core_target(tmp_path)
    integration = _integration_target(tmp_path, "github")
    _write_pyproject(core.pyproject_path)
    _write_pyproject(integration.pyproject_path)
    release_rel = ".ocean-release/core/combined.yaml"
    _write_release(tmp_path / release_rel)

    git = FakeGit(
        repo_root=tmp_path,
        targets=[core, integration],
        release_files=[release_rel],
    )

    assert validate(git, base_ref="origin/main", head_ref="HEAD") == []


def test_integration_only_still_requires_own_release(tmp_path: Path) -> None:
    integration = _integration_target(tmp_path, "github")
    _write_pyproject(integration.pyproject_path)

    git = FakeGit(repo_root=tmp_path, targets=[integration])

    errors = validate(git, base_ref="origin/main", head_ref="HEAD")
    assert len(errors) == 1
    assert "github" in errors[0]
    assert "release file" in errors[0]


def test_core_plus_integration_without_any_intent_fails(tmp_path: Path) -> None:
    core = _core_target(tmp_path)
    integration = _integration_target(tmp_path, "jira")
    _write_pyproject(core.pyproject_path)
    _write_pyproject(integration.pyproject_path)

    git = FakeGit(repo_root=tmp_path, targets=[core, integration])

    errors = validate(git, base_ref="origin/main", head_ref="HEAD")
    assert len(errors) == 2
    assert any("ocean-core" in error for error in errors)
    assert any("jira" in error for error in errors)


def test_integration_intent_still_required_when_only_core_changed_elsewhere(
    tmp_path: Path,
) -> None:
    """A core intent without a core code change does not cover integrations."""
    integration = _integration_target(tmp_path, "github")
    _write_pyproject(integration.pyproject_path)
    release_rel = ".ocean-release/core/orphan.yaml"
    _write_release(tmp_path / release_rel)

    git = FakeGit(
        repo_root=tmp_path,
        targets=[integration],
        release_files=[release_rel],
    )

    errors = validate(git, base_ref="origin/main", head_ref="HEAD")
    assert len(errors) == 1
    assert "github" in errors[0]
