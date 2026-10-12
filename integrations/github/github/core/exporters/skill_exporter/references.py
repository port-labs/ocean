from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from github.core.exporters.skill_exporter.utils import SKILL_MD_FILENAME

TEXT_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".md",
        ".mdx",
        ".markdown",
        ".txt",
        ".rst",
        ".json",
        ".jsonl",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".csv",
        ".tsv",
        ".xml",
        ".html",
        ".htm",
        ".css",
        ".sql",
        ".py",
        ".sh",
        ".bash",
        ".ps1",
        ".js",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".jsx",
        ".rb",
        ".go",
        ".java",
        ".rs",
        ".tf",
    }
)
MAX_SKILL_BUNDLE_SIZE = 1024 * 1024
MAX_REFERENCE_DEPTH = 5
# Git tree mode for symlinks: their "content" is a target path that may point
# outside the skill folder, so they are never bundled.
SYMLINK_MODE = "120000"


def skill_dir_prefix(skill_md_path: str) -> str:
    """Path prefix shared by every file inside the skill folder ("" at repo root)."""
    skill_dir = str(PurePosixPath(skill_md_path).parent)
    return "" if skill_dir == "." else f"{skill_dir}/"


def select_reference_files(
    tree: list[dict[str, Any]], skill_md_path: str
) -> list[dict[str, Any]]:
    """Pick the text files in a skill's folder from an already fetched git tree.

    Files that belong to a nested skill (a subfolder with its own SKILL.md)
    are left to that skill.
    """
    prefix = skill_dir_prefix(skill_md_path)
    candidates = [
        entry
        for entry in tree
        if entry.get("type") == "blob"
        and entry.get("mode") != SYMLINK_MODE
        and entry["path"].startswith(prefix)
        and entry["path"] != skill_md_path
    ]
    nested_skill_prefixes = tuple(
        entry["path"].removesuffix(SKILL_MD_FILENAME)
        for entry in candidates
        if PurePosixPath(entry["path"]).name == SKILL_MD_FILENAME
    )

    selected = []
    for entry in candidates:
        relative_path = entry["path"].removeprefix(prefix)
        if (
            relative_path.count("/") <= MAX_REFERENCE_DEPTH
            and PurePosixPath(relative_path).suffix.lower() in TEXT_FILE_EXTENSIONS
            and not entry["path"].startswith(nested_skill_prefixes)
        ):
            selected.append(entry)
    return selected


def get_bundle_size(skill_md_size: int, references: list[dict[str, Any]]) -> int:
    """Total bytes of SKILL.md plus its references, using sizes from the git tree."""
    return skill_md_size + sum(entry.get("size", 0) for entry in references)
