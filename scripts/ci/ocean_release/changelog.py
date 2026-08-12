"""Towncrier changelog application."""

from __future__ import annotations

import subprocess
import sys
import uuid
from pathlib import Path

from .models import ReleaseTarget


def apply_towncrier_changelog(
    target: ReleaseTarget,
    new_version: str,
    changelog_type: str,
    message: str,
) -> None:
    fragment = f"+{uuid.uuid4().hex[:8]}.{changelog_type}.md"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "towncrier",
            "create",
            "--content",
            message,
            fragment,
        ],
        cwd=target.work_dir,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "towncrier",
            "build",
            "--yes",
            "--name",
            target.label,
            "--version",
            new_version,
        ],
        cwd=target.work_dir,
        check=True,
    )
    changelog_dir = Path(target.work_dir, "changelog")
    if changelog_dir.exists():
        for fragment_path in changelog_dir.glob("*.md"):
            fragment_path.unlink()


def cleanup_release_file(release_path: Path) -> None:
    release_path.unlink(missing_ok=True)
    release_dir = release_path.parent
    if not release_dir.exists():
        return
    for child in release_dir.iterdir():
        if child.name != "README.md":
            child.unlink(missing_ok=True)
