from __future__ import annotations

import io
from typing import Any

SKILL_MD_PATH = "SKILL.md"


def package_skill_files(
    skill_directory: str,
    instructions: str,
    resources: list[dict[str, Any]] | None = None,
) -> list[tuple[str, io.BytesIO]]:
    """Build Anthropic skill upload files under a single top-level directory.

    ``instructions`` maps to ``SKILL.md``; each entry in ``resources`` is an
    additional file (path + content) returned by the ai-service content API.
    """
    packaged: list[tuple[str, io.BytesIO]] = [
        (
            f"{skill_directory}/{SKILL_MD_PATH}",
            io.BytesIO(instructions.encode("utf-8")),
        )
    ]

    for resource in resources or []:
        path = resource.get("path")
        content = resource.get("content")
        if not isinstance(path, str) or not path:
            continue
        if not isinstance(content, str):
            continue
        normalized = path.lstrip("/")
        if normalized == SKILL_MD_PATH or normalized.endswith(f"/{SKILL_MD_PATH}"):
            continue
        packaged.append(
            (f"{skill_directory}/{normalized}", io.BytesIO(content.encode("utf-8")))
        )

    return packaged


def skill_display_title(skill_content: dict[str, Any]) -> str:
    """Return the display title from an ai-service skill content response."""
    title = skill_content.get("title")
    if isinstance(title, str) and title:
        return title
    name = skill_content.get("name")
    if isinstance(name, str) and name:
        return name
    raise ValueError("Port skill content is missing title and name")


def claude_skill_raw_from_api(skill: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": skill["id"],
        "display_title": skill.get("display_title"),
        "source": skill.get("source", "custom"),
        "latest_version": skill.get("latest_version"),
        "created_at": skill.get("created_at"),
        "updated_at": skill.get("updated_at"),
    }
