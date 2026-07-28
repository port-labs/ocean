from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field
from ruamel.yaml import YAML
from wcmatch import glob

from github.helpers.utils import matches_glob_pattern

DEFAULT_SKILL_PATHS: list[str] = [
    ".agents/skills/**/SKILL.md",
    ".agent/skills/**/SKILL.md",
    ".cursor/skills/**/SKILL.md",
    ".claude/skills/**/SKILL.md",
    ".codex/skills/**/SKILL.md",
    ".github/skills/**/SKILL.md",
    ".opencode/skills/**/SKILL.md",
    "skills/**/SKILL.md",
]

SKILL_MD_FILENAME = "SKILL.md"


class Skill(BaseModel):
    """Normalized Agent Skill parsed out of a single SKILL.md file."""

    name: str
    description: str = ""
    instructions: str = ""
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    path: str
    skill_md_path: str = Field(serialization_alias="skillMdPath")
    root: str


class SkillRawItem(BaseModel):
    """Raw item emitted for the `skill` kind, by both resync and webhooks."""

    skill: Skill
    repository: dict[str, Any] = Field(serialization_alias="__repository")
    branch: str = Field(serialization_alias="__branch")
    organization: Optional[str] = Field(
        default=None, serialization_alias="__organization"
    )


def _glob_root(pattern: str) -> str:
    """Strip the SKILL.md suffix from a glob to get the configured root prefix."""
    cleaned = pattern.strip("/")
    suffixes = (
        f"/**/{SKILL_MD_FILENAME}",
        f"/{SKILL_MD_FILENAME}",
        f"**/{SKILL_MD_FILENAME}",
        SKILL_MD_FILENAME,
    )
    lower = cleaned.lower()
    for suffix in suffixes:
        if lower.endswith(suffix.lower()):
            return cleaned[: -len(suffix)].strip("/")
    return cleaned


def _infer_skill_root(skill_md_path: str, path_globs: list[str]) -> str:
    """Root that matched this SKILL.md, for mapping filters."""
    for pattern in path_globs:
        if matches_glob_pattern(skill_md_path, pattern, flags=glob.DOTGLOB):
            root = _glob_root(pattern)
            if root:
                return root
    skill_dir = str(Path(skill_md_path).parent).replace("\\", "/")
    parent = str(Path(skill_dir).parent).replace("\\", "/")
    return parent if parent not in (".", "") else skill_dir


def _parse_skill_markdown(content: str) -> tuple[dict[str, Any], str]:
    """Split SKILL.md into YAML frontmatter and markdown body."""
    text = content.replace("\r\n", "\n")
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    raw_fm = parts[1].strip()
    body = parts[2].lstrip("\n")
    if not raw_fm:
        return {}, body

    try:
        parsed = YAML(typ="safe").load(raw_fm)
    except Exception as exc:
        logger.warning(f"Failed to parse skill frontmatter: {exc}")
        return {}, body

    if isinstance(parsed, dict):
        return parsed, body
    logger.warning("Skill frontmatter did not parse to a mapping; ignoring")
    return {}, body


def _build_skill(
    *,
    skill_md_path: str,
    content: str,
    path_globs: list[str],
) -> Skill:
    frontmatter, body = _parse_skill_markdown(content)
    path_obj = Path(skill_md_path)
    skill_dir = str(path_obj.parent).replace("\\", "/")

    name = frontmatter.get("name")
    if not isinstance(name, str) or not name.strip():
        name = path_obj.parent.name

    description = frontmatter.get("description")
    if not isinstance(description, str):
        description = ""

    return Skill(
        name=name,
        description=description,
        instructions=body,
        frontmatter=frontmatter,
        path=skill_dir,
        skill_md_path=skill_md_path,
        root=_infer_skill_root(skill_md_path, path_globs),
    )


def build_skill_raw_item(
    *,
    skill_md_path: str,
    content: str,
    repository: dict[str, Any],
    branch: str,
    path_globs: list[str],
    organization: Optional[str] = None,
) -> dict[str, Any]:
    """Single entry point for building a skill raw item.

    Webhook deletes call this with an empty ``content`` so that deleted entities
    carry the exact same identifiers as the upserted ones.
    """
    return SkillRawItem(
        skill=_build_skill(
            skill_md_path=skill_md_path,
            content=content,
            path_globs=path_globs,
        ),
        repository=repository,
        branch=branch,
        organization=organization,
    ).model_dump(by_alias=True)
