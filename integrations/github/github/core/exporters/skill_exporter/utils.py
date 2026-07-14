from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from loguru import logger
from ruamel.yaml import YAML

DEFAULT_SKILL_ROOTS: list[str] = [
    ".agents/skills",
    ".agent/skills",
    ".cursor/skills",
    ".claude/skills",
    ".codex/skills",
    ".github/skills",
    ".opencode/skills",
    "skills",
]

SKILL_MD_FILENAME = "SKILL.md"

SkillContentMode = Literal["frontmatter", "skill.md"]


def roots_to_globs(roots: list[str]) -> list[str]:
    """Convert skill roots to GitHub tree globs that match SKILL.md files."""
    globs: list[str] = []
    for root in roots:
        clean = root.strip().strip("/")
        if not clean:
            continue
        globs.append(f"{clean}/**/{SKILL_MD_FILENAME}")
        globs.append(f"{clean}/{SKILL_MD_FILENAME}")
    return globs


def match_skill_root(skill_md_path: str, roots: list[str]) -> str | None:
    """Return the configured root that owns this SKILL.md path, if any."""
    normalized = skill_md_path.strip("/")
    for root in roots:
        clean = root.strip().strip("/")
        if normalized == f"{clean}/{SKILL_MD_FILENAME}":
            return clean
        if normalized.startswith(f"{clean}/") and normalized.endswith(
            f"/{SKILL_MD_FILENAME}"
        ):
            return clean
    return None


def path_under_roots_or_extra(
    skill_md_path: str, roots: list[str], extra_paths: list[str]
) -> bool:
    if match_skill_root(skill_md_path, roots) is not None:
        return True
    from github.helpers.utils import matches_glob_pattern

    for pattern in extra_paths:
        if matches_glob_pattern(skill_md_path, pattern):
            return True
    return False


def parse_skill_markdown(content: str) -> tuple[dict[str, Any], str]:
    """
    Split SKILL.md into YAML frontmatter and markdown body.

    Returns (frontmatter_dict, body). On missing/invalid frontmatter returns
    ({}, full content as body).
    """
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
        yaml = YAML(typ="safe")
        parsed = yaml.load(raw_fm)
    except Exception as exc:
        logger.warning(f"Failed to parse skill frontmatter: {exc}")
        return {}, body

    if isinstance(parsed, dict):
        return parsed, body
    logger.warning("Skill frontmatter did not parse to a mapping; ignoring")
    return {}, body


def build_skill_object(
    *,
    skill_md_path: str,
    content: str,
    content_mode: SkillContentMode,
    roots: list[str] | None = None,
) -> dict[str, Any]:
    """Build the normalized `.skill` object from SKILL.md path and content."""
    roots = roots or DEFAULT_SKILL_ROOTS
    frontmatter, body = parse_skill_markdown(content)
    path_obj = Path(skill_md_path)
    skill_dir = str(path_obj.parent).replace("\\", "/")
    path_name = path_obj.parent.name

    name = frontmatter.get("name")
    if not isinstance(name, str) or not name.strip():
        name = path_name

    description = frontmatter.get("description")
    if not isinstance(description, str):
        description = ""

    root = match_skill_root(skill_md_path, roots) or skill_dir.split("/")[0]

    skill: dict[str, Any] = {
        "name": name,
        "description": description,
        "instructions": None,
        "frontmatter": frontmatter,
        "path": skill_dir,
        "skillMdPath": skill_md_path,
        "root": root,
    }

    if content_mode == "skill.md":
        skill["instructions"] = body

    return skill


def build_skill_raw_item(
    *,
    skill_md_path: str,
    content: str,
    content_mode: SkillContentMode,
    repository: dict[str, Any],
    branch: str,
    organization: str | None = None,
    roots: list[str] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "skill": build_skill_object(
            skill_md_path=skill_md_path,
            content=content,
            content_mode=content_mode,
            roots=roots,
        ),
        "repository": repository,
        "branch": branch,
    }
    if organization is not None:
        item["organization"] = organization
    return item
