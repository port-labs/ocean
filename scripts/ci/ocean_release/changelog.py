"""Towncrier changelog application."""

from __future__ import annotations

import re
import subprocess
import sys
import uuid
from pathlib import Path

from .models import ReleaseTarget

_VERSION_HEADER = re.compile(r"(?m)^## ")
_TOWNCRIER_START = "<!-- towncrier release notes start -->"


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
    _flatten_latest_release_sibling_dashes(target.changelog_path)
    changelog_dir = Path(target.work_dir, "changelog")
    if changelog_dir.exists():
        for fragment_path in changelog_dir.glob("*.md"):
            fragment_path.unlink()


def _flatten_latest_release_sibling_dashes(changelog_path: Path) -> None:
    """Towncrier indents fragment continuation lines, which nests '-' bullets."""
    text = changelog_path.read_text(encoding="utf-8")
    if _TOWNCRIER_START not in text:
        return
    prefix, rest = text.split(_TOWNCRIER_START, 1)
    headers = list(_VERSION_HEADER.finditer(rest))
    if not headers:
        return
    start = headers[0].start()
    end = headers[1].start() if len(headers) > 1 else len(rest)
    latest = re.sub(r"(?m)^  - ", "- ", rest[start:end])
    latest = re.sub(r"(?m)^  \\-", "  -", latest)
    changelog_path.write_text(
        f"{prefix}{_TOWNCRIER_START}{rest[:start]}{latest}{rest[end:]}",
        encoding="utf-8",
    )


def cleanup_release_file(release_path: Path) -> None:
    release_path.unlink(missing_ok=True)
    release_dir = release_path.parent
    if not release_dir.exists():
        return
    for child in release_dir.iterdir():
        if child.name != "README.md":
            child.unlink(missing_ok=True)
