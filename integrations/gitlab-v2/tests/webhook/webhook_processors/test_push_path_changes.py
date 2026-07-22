from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from gitlab.webhook.webhook_processors.push_constants import DELETED_COMMIT_SHA
from gitlab.webhook.webhook_processors.push_path_changes import (
    collect_paths_from_commits,
    paths_from_compare_diffs,
    resolve_push_path_changes,
)


def test_collect_paths_from_commits() -> None:
    payload = {
        "commits": [
            {
                "added": ["a.md"],
                "modified": ["b.md"],
                "removed": ["c.md"],
            },
            {
                "added": [],
                "modified": ["d.md"],
                "removed": ["a.md"],
            },
        ]
    }
    changed, removed = collect_paths_from_commits(payload)
    assert changed == {"a.md", "b.md", "d.md"}
    assert removed == {"c.md", "a.md"}


def test_paths_from_compare_diffs() -> None:
    diffs = [
        {
            "new_path": "added.md",
            "old_path": "added.md",
            "new_file": True,
            "deleted_file": False,
        },
        {
            "new_path": "gone.md",
            "old_path": "gone.md",
            "new_file": False,
            "deleted_file": True,
        },
        {
            "new_path": "new-name.md",
            "old_path": "old-name.md",
            "renamed_file": True,
            "deleted_file": False,
        },
    ]
    changed, removed = paths_from_compare_diffs(diffs)
    assert changed == {"added.md", "new-name.md"}
    assert removed == {"gone.md", "old-name.md"}


@pytest.mark.asyncio
async def test_resolve_push_path_changes_uses_commits_when_complete() -> None:
    client = MagicMock()
    payload: dict[str, Any] = {
        "before": "aaa",
        "after": "bbb",
        "total_commits_count": 1,
        "commits": [
            {"added": ["skills/x/SKILL.md"], "modified": [], "removed": []},
        ],
    }
    changed, removed = await resolve_push_path_changes(client, "group/project", payload)
    assert changed == {"skills/x/SKILL.md"}
    assert removed == set()
    client.compare_repository.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_push_path_changes_uses_compare_when_truncated() -> None:
    client = MagicMock()
    client.compare_repository = AsyncMock(
        return_value={
            "diffs": [
                {
                    "new_path": "skills/y/SKILL.md",
                    "old_path": "skills/y/SKILL.md",
                    "new_file": True,
                    "deleted_file": False,
                }
            ]
        }
    )
    payload: dict[str, Any] = {
        "before": "aaa",
        "after": "bbb",
        "total_commits_count": 10,
        "commits": [
            {"added": ["README.md"], "modified": [], "removed": []},
        ],
    }
    changed, removed = await resolve_push_path_changes(client, "group/project", payload)
    client.compare_repository.assert_awaited_once_with("group/project", "aaa", "bbb")
    assert changed == {"skills/y/SKILL.md"}
    assert removed == set()


@pytest.mark.asyncio
async def test_resolve_push_path_changes_skips_compare_on_blank_sha() -> None:
    client = MagicMock()
    payload: dict[str, Any] = {
        "before": DELETED_COMMIT_SHA,
        "after": "bbb",
        "total_commits_count": 5,
        "commits": [
            {"added": ["skills/z/SKILL.md"], "modified": [], "removed": []},
        ],
    }
    changed, removed = await resolve_push_path_changes(client, "group/project", payload)
    assert changed == {"skills/z/SKILL.md"}
    client.compare_repository.assert_not_called()
