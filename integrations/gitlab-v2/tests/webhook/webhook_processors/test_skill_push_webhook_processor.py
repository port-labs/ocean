from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from gitlab.helpers.skill_plugin import DEFAULT_SKILL_PATHS
from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors.push_constants import DELETED_COMMIT_SHA
from gitlab.webhook.webhook_processors.skill_push_webhook_processor import (
    SkillPushWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


def make_skill_resource_config(
    paths: list[str] | None = None,
    repos: list[str] | None = None,
) -> MagicMock:
    config = MagicMock()
    path_entries = []
    for path in paths or DEFAULT_SKILL_PATHS:
        entry = MagicMock()
        entry.path = path
        entry.repos = repos or []
        path_entries.append(entry)
    config.selector.paths = path_entries
    config.kind = "skill"
    return config


@pytest.mark.asyncio
class TestSkillPushWebhookProcessor:
    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Push Hook"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> SkillPushWebhookProcessor:
        return SkillPushWebhookProcessor(event=mock_event)

    @pytest.fixture
    def base_payload(self) -> dict[str, Any]:
        return {
            "object_kind": "push",
            "before": "aaa111",
            "after": "bbb222",
            "ref": "refs/heads/main",
            "total_commits_count": 1,
            "project": {
                "id": 42,
                "name": "project",
                "path": "project",
                "path_with_namespace": "group/project",
                "default_branch": "main",
            },
            "commits": [
                {
                    "added": [".cursor/skills/hello/SKILL.md"],
                    "modified": [],
                    "removed": [],
                }
            ],
        }

    async def test_get_matching_kinds(
        self, processor: SkillPushWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.SKILL]

    async def test_skips_non_default_branch(
        self,
        processor: SkillPushWebhookProcessor,
        base_payload: dict[str, Any],
    ) -> None:
        payload = {**base_payload, "ref": "refs/heads/feature"}
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(payload, make_skill_resource_config())

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
        processor._gitlab_webhook_client.compare_repository.assert_not_called()

    async def test_skips_branch_delete(
        self,
        processor: SkillPushWebhookProcessor,
        base_payload: dict[str, Any],
    ) -> None:
        payload = {**base_payload, "after": DELETED_COMMIT_SHA}
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(payload, make_skill_resource_config())

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_delete_stub_shape(
        self,
        processor: SkillPushWebhookProcessor,
        base_payload: dict[str, Any],
    ) -> None:
        payload = {
            **base_payload,
            "commits": [
                {
                    "added": [],
                    "modified": [],
                    "removed": [".agents/skills/demo/SKILL.md"],
                }
            ],
        }
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(payload, make_skill_resource_config())

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1
        deleted = result.deleted_raw_results[0]
        assert deleted["skill"]["skillMdPath"] == ".agents/skills/demo/SKILL.md"
        assert deleted["skill"]["path"] == ".agents/skills/demo"
        assert deleted["skill"]["root"] == ".agents/skills"
        assert deleted["repo"]["path_with_namespace"] == "group/project"
        assert deleted["__branch"] == "main"

    async def test_upsert_from_changed_skill(
        self,
        processor: SkillPushWebhookProcessor,
        base_payload: dict[str, Any],
    ) -> None:
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client._process_file_batch = AsyncMock(
            return_value=[
                {
                    "path": ".cursor/skills/hello/SKILL.md",
                    "content": "---\nname: hello\ndescription: hi\n---\nbody",
                    "ref": "bbb222",
                }
            ]
        )
        processor._gitlab_webhook_client._enrich_files_with_repos = AsyncMock(
            return_value=[
                {
                    "file": {
                        "path": ".cursor/skills/hello/SKILL.md",
                        "content": "---\nname: hello\ndescription: hi\n---\nbody",
                        "ref": "bbb222",
                    },
                    "repo": base_payload["project"],
                }
            ]
        )

        result = await processor.handle_event(
            base_payload, make_skill_resource_config()
        )

        assert len(result.updated_raw_results) == 1
        skill = result.updated_raw_results[0]["skill"]
        assert skill["name"] == "hello"
        assert skill["skillMdPath"] == ".cursor/skills/hello/SKILL.md"
        assert result.deleted_raw_results == []

    async def test_truncated_push_uses_compare_api(
        self,
        processor: SkillPushWebhookProcessor,
        base_payload: dict[str, Any],
    ) -> None:
        payload = {
            **base_payload,
            "total_commits_count": 5,
            "commits": [
                {
                    "added": ["README.md"],
                    "modified": [],
                    "removed": [],
                }
            ],
        }
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.compare_repository = AsyncMock(
            return_value={
                "diffs": [
                    {
                        "new_path": ".cursor/skills/from-compare/SKILL.md",
                        "old_path": ".cursor/skills/from-compare/SKILL.md",
                        "new_file": True,
                        "deleted_file": False,
                    }
                ]
            }
        )
        processor._gitlab_webhook_client._process_file_batch = AsyncMock(
            return_value=[
                {
                    "path": ".cursor/skills/from-compare/SKILL.md",
                    "content": "---\nname: from-compare\ndescription: x\n---\n",
                    "ref": "bbb222",
                }
            ]
        )
        processor._gitlab_webhook_client._enrich_files_with_repos = AsyncMock(
            return_value=[
                {
                    "file": {
                        "path": ".cursor/skills/from-compare/SKILL.md",
                        "content": "---\nname: from-compare\ndescription: x\n---\n",
                        "ref": "bbb222",
                    },
                    "repo": payload["project"],
                }
            ]
        )

        result = await processor.handle_event(payload, make_skill_resource_config())

        processor._gitlab_webhook_client.compare_repository.assert_awaited_once_with(
            "group/project", "aaa111", "bbb222"
        )
        assert len(result.updated_raw_results) == 1
        assert (
            result.updated_raw_results[0]["skill"]["skillMdPath"]
            == ".cursor/skills/from-compare/SKILL.md"
        )
