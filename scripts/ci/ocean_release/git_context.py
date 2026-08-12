"""Git operations for Ocean release CI."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .models import ReleaseTarget
from .version import parse_version


@dataclass
class GitContext:
    repo_root: Path

    def run_git(
        self, *args: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=check,
        )

    def checkout_detach(self, ref: str, *, fetch_ref: str | None = None) -> None:
        if fetch_ref is not None:
            remote, branch = (
                fetch_ref.split("/", 1) if "/" in fetch_ref else ("origin", fetch_ref)
            )
            self.run_git("fetch", remote, branch, check=False)
        self.run_git("checkout", "--detach", ref)

    def commit_all(self, message: str) -> None:
        self.run_git("add", "-A")
        self.run_git("commit", "-m", message)

    def read_at_ref(self, ref: str, path: Path) -> str:
        rel = path.relative_to(self.repo_root).as_posix()
        result = self.run_git("show", f"{ref}:{rel}", check=False)
        if result.returncode != 0:
            return ""
        return result.stdout

    def read_worktree(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def changed_files(self, base_ref: str, head_ref: str) -> list[str]:
        result = self.run_git("diff", "--name-only", f"{base_ref}...{head_ref}")
        return [line for line in result.stdout.splitlines() if line]

    def changed_release_targets(
        self, base_ref: str, head_ref: str
    ) -> list[ReleaseTarget]:
        return self.discover_targets(self.changed_files(base_ref, head_ref))

    def discover_targets(self, changed_files: list[str]) -> list[ReleaseTarget]:
        targets: dict[str, ReleaseTarget] = {}
        for file_path in changed_files:
            if file_path.startswith("integrations/"):
                parts = Path(file_path).parts
                if len(parts) >= 2:
                    name = parts[1]
                    pyproject_path = Path(
                        self.repo_root, "integrations", name, "pyproject.toml"
                    )
                    if not pyproject_path.exists():
                        continue  # e.g. integrations/_infra — not a releasable integration
                    targets[f"integration:{name}"] = ReleaseTarget(
                        kind="integration",
                        name=name,
                        pyproject_path=pyproject_path,
                        changelog_path=Path(
                            self.repo_root, "integrations", name, "CHANGELOG.md"
                        ),
                    )
            elif file_path.startswith("port_ocean/") or file_path == "pyproject.toml":
                targets["core:core"] = ReleaseTarget(
                    kind="core",
                    name="core",
                    pyproject_path=Path(self.repo_root, "pyproject.toml"),
                    changelog_path=Path(self.repo_root, "CHANGELOG.md"),
                )
        return list(targets.values())

    def has_version_changed(
        self, base_ref: str, head_ref: str, pyproject: Path
    ) -> bool:
        rel = pyproject.relative_to(self.repo_root).as_posix()
        if rel not in self.changed_files(base_ref, head_ref):
            return False
        base_content = self.read_at_ref(base_ref, pyproject)
        if not base_content:
            return True  # pyproject added in this PR — no version on base to compare
        head_content = self.read_worktree(pyproject)
        return parse_version(base_content) != parse_version(head_content)

    def has_changelog_changed(
        self, base_ref: str, head_ref: str, changelog: Path
    ) -> bool:
        rel = changelog.relative_to(self.repo_root).as_posix()
        return rel in self.changed_files(base_ref, head_ref)

    def release_files_added_in_diff(
        self, base_ref: str, head_ref: str | None = None
    ) -> list[str]:
        if head_ref is None:
            diff_args: tuple[str, ...] = (f"{base_ref}^", base_ref)
        else:
            diff_args = (f"{base_ref}...{head_ref}",)
        result = self.run_git(
            "diff",
            "--name-only",
            "--diff-filter=A",
            *diff_args,
            check=False,
        )
        return (
            sorted(
                line
                for line in result.stdout.splitlines()
                if ".ocean-release/" in line and line.endswith((".yaml", ".yml"))
            )
            if result.returncode == 0
            else []
        )
