from __future__ import annotations

import io

import pytest

from actions.skill_packaging import (
    SKILL_MD_PATH,
    claude_skill_raw_from_api,
    package_skill_files,
    skill_display_title,
)


def test_package_skill_files_includes_skill_md_from_instructions() -> None:
    files = package_skill_files("my-skill", "# Skill instructions")

    paths = [path for path, _ in files]
    assert paths == [f"my-skill/{SKILL_MD_PATH}"]
    content = files[0][1].read().decode()
    assert content == "# Skill instructions"
    assert all(isinstance(stream, io.BytesIO) for _, stream in files)


def test_package_skill_files_includes_extra_resources() -> None:
    files = package_skill_files(
        "my-skill",
        "# Skill",
        resources=[
            {"path": "helpers/run.py", "content": "print('ok')"},
        ],
    )

    paths = [path for path, _ in files]
    assert paths == [f"my-skill/{SKILL_MD_PATH}", "my-skill/helpers/run.py"]


def test_package_skill_files_skips_duplicate_skill_md_in_resources() -> None:
    files = package_skill_files(
        "my-skill",
        "# Skill",
        resources=[
            {"path": SKILL_MD_PATH, "content": "duplicate"},
        ],
    )

    paths = [path for path, _ in files]
    assert paths == [f"my-skill/{SKILL_MD_PATH}"]
    content = files[0][1].read().decode()
    assert content == "# Skill"


def test_package_skill_files_skips_resources_with_missing_fields() -> None:
    files = package_skill_files(
        "my-skill",
        "# Skill",
        resources=[
            {"path": "ok.py", "content": "x = 1"},
            {"path": "no-content.py"},
            {"content": "no-path"},
        ],
    )

    paths = [path for path, _ in files]
    assert "my-skill/ok.py" in paths
    assert not any("no-content" in p or "no-path" in p for p in paths)


def test_skill_display_title_prefers_title() -> None:
    content = {"title": "My Skill", "name": "my-skill", "instructions": "# Skill"}
    assert skill_display_title(content) == "My Skill"


def test_skill_display_title_falls_back_to_name() -> None:
    content = {"name": "my-skill", "instructions": "# Skill"}
    assert skill_display_title(content) == "my-skill"


def test_skill_display_title_raises_when_both_missing() -> None:
    with pytest.raises(ValueError, match="missing title and name"):
        skill_display_title({"instructions": "# Skill"})


def test_claude_skill_raw_from_api_maps_fields() -> None:
    raw = claude_skill_raw_from_api(
        {
            "id": "skill_01",
            "display_title": "Demo",
            "source": "custom",
            "latest_version": "skillver_01",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-02T00:00:00Z",
        }
    )

    assert raw == {
        "id": "skill_01",
        "display_title": "Demo",
        "source": "custom",
        "latest_version": "skillver_01",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
    }
