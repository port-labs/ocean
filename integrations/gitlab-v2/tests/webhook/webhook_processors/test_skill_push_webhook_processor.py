from typing import Any, AsyncIterator
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
    include_skill_folder: bool = False,
) -> MagicMock:
    config = MagicMock()
    path_entries = []
    for path in paths or DEFAULT_SKILL_PATHS:
        entry = MagicMock()
        entry.path = path
        entry.repos = repos or []
        path_entries.append(entry)
    config.selector.paths = path_entries
    config.selector.include_skill_folder = include_skill_folder
    config.kind = "skill"
    return config


def compare_diffs(
    added: list[str] | None = None,
    deleted: list[str] | None = None,
    modified: list[str] | None = None,
) -> dict[str, Any]:
    diffs: list[dict[str, Any]] = [
        {"new_path": path, "old_path": path, "new_file": True, "deleted_file": False}
        for path in added or []
    ]
    diffs.extend(
        {"new_path": path, "old_path": path, "deleted_file": True}
        for path in deleted or []
    )
    diffs.extend(
        {"new_path": path, "old_path": path, "new_file": False, "deleted_file": False}
        for path in modified or []
    )
    return {"diffs": diffs}


SKILL_MD = "---\nname: hello\ndescription: hi\n---\nbody"


def make_folder_client(
    project: dict[str, Any],
    diffs: dict[str, Any],
    tree: list[str],
    contents: dict[str, str] | None = None,
) -> MagicMock:
    """Webhook client whose repository holds `tree` at every ref."""
    client = MagicMock()
    client.compare_repository = AsyncMock(return_value=diffs)
    client._process_file_batch = AsyncMock(
        side_effect=lambda batch, context, skip_parsing: [
            {**file, "content": SKILL_MD} for file in batch
        ]
    )
    client._enrich_files_with_repos = AsyncMock(
        side_effect=lambda files: [{"file": file, "repo": project} for file in files]
    )
    client.tree_calls = []

    async def get_repository_tree(
        _project: dict[str, Any], path: str, ref: str, *, recursive: bool
    ) -> AsyncIterator[list[dict[str, Any]]]:
        client.tree_calls.append((path, ref))
        prefix = f"{path}/" if path else ""
        yield [
            {"type": "blob", "path": entry}
            for entry in tree
            if entry.startswith(prefix)
        ]

    client.get_repository_tree = get_repository_tree
    client.rest.get_file_data = AsyncMock(
        side_effect=lambda project_id, path, ref: {"content": (contents or {})[path]}
    )
    return client


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

    async def test_skips_when_default_branch_unknown(
        self,
        processor: SkillPushWebhookProcessor,
        base_payload: dict[str, Any],
    ) -> None:
        project = {**base_payload["project"]}
        project.pop("default_branch")
        payload = {**base_payload, "project": project}
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
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.compare_repository = AsyncMock(
            return_value=compare_diffs(deleted=[".agents/skills/demo/SKILL.md"])
        )

        result = await processor.handle_event(
            base_payload, make_skill_resource_config()
        )

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
        processor._gitlab_webhook_client.compare_repository = AsyncMock(
            return_value=compare_diffs(added=[".cursor/skills/hello/SKILL.md"])
        )
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

        processor._gitlab_webhook_client.compare_repository.assert_awaited_once_with(
            "group/project", "aaa111", "bbb222"
        )
        assert len(result.updated_raw_results) == 1
        skill = result.updated_raw_results[0]["skill"]
        assert skill["name"] == "hello"
        assert skill["skillMdPath"] == ".cursor/skills/hello/SKILL.md"
        assert result.deleted_raw_results == []

    async def test_falls_back_to_commits_when_compare_fails(
        self,
        processor: SkillPushWebhookProcessor,
        base_payload: dict[str, Any],
    ) -> None:
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.compare_repository = AsyncMock(
            side_effect=RuntimeError("compare unavailable")
        )
        processor._gitlab_webhook_client._process_file_batch = AsyncMock(
            return_value=[
                {
                    "path": ".cursor/skills/hello/SKILL.md",
                    "content": "---\nname: hello\n---\n",
                    "ref": "bbb222",
                }
            ]
        )
        processor._gitlab_webhook_client._enrich_files_with_repos = AsyncMock(
            return_value=[
                {
                    "file": {
                        "path": ".cursor/skills/hello/SKILL.md",
                        "content": "---\nname: hello\n---\n",
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
        assert (
            result.updated_raw_results[0]["skill"]["skillMdPath"]
            == ".cursor/skills/hello/SKILL.md"
        )


@pytest.mark.asyncio
class TestSkillPushWebhookSkillFolder:
    @pytest.fixture
    def processor(self) -> SkillPushWebhookProcessor:
        return SkillPushWebhookProcessor(
            event=WebhookEvent(
                trace_id="test-trace-id",
                headers={"x-gitlab-event": "Push Hook"},
                payload={},
            )
        )

    @pytest.fixture
    def payload(self) -> dict[str, Any]:
        return {
            "object_kind": "push",
            "before": "aaa111",
            "after": "bbb222",
            "ref": "refs/heads/main",
            "project": {
                "id": 42,
                "path_with_namespace": "group/project",
                "default_branch": "main",
            },
            "commits": [],
        }

    @staticmethod
    def _config(include_skill_folder: bool = True) -> MagicMock:
        return make_skill_resource_config(
            paths=["skills/**/SKILL.md"], include_skill_folder=include_skill_folder
        )

    async def test_folder_file_change_rebuilds_skill_at_pushed_commit(
        self, processor: SkillPushWebhookProcessor, payload: dict[str, Any]
    ) -> None:
        client = make_folder_client(
            payload["project"],
            compare_diffs(modified=["skills/hello/references/api.md"]),
            tree=["skills/hello/SKILL.md", "skills/hello/references/api.md"],
            contents={"skills/hello/references/api.md": "# API v2"},
        )
        processor._gitlab_webhook_client = client

        result = await processor.handle_event(payload, self._config())

        assert len(result.updated_raw_results) == 1
        skill = result.updated_raw_results[0]["skill"]
        assert skill["skillMdPath"] == "skills/hello/SKILL.md"
        assert skill["files"] == [{"path": "references/api.md", "content": "# API v2"}]
        assert result.deleted_raw_results == []
        assert client.tree_calls == [("skills", "bbb222"), ("skills/hello", "bbb222")]
        file_batch = client._process_file_batch.call_args.args[0]
        assert file_batch == [
            {"project_id": "42", "path": "skills/hello/SKILL.md", "ref": "bbb222"}
        ]

    async def test_folder_file_change_ignored_when_flag_off(
        self, processor: SkillPushWebhookProcessor, payload: dict[str, Any]
    ) -> None:
        client = make_folder_client(
            payload["project"],
            compare_diffs(modified=["skills/hello/references/api.md"]),
            tree=["skills/hello/SKILL.md", "skills/hello/references/api.md"],
        )
        processor._gitlab_webhook_client = client

        result = await processor.handle_event(
            payload, self._config(include_skill_folder=False)
        )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
        assert client.tree_calls == []

    async def test_deleted_skill_folder_is_only_deleted(
        self, processor: SkillPushWebhookProcessor, payload: dict[str, Any]
    ) -> None:
        client = make_folder_client(
            payload["project"],
            compare_diffs(
                deleted=["skills/hello/SKILL.md", "skills/hello/references/api.md"]
            ),
            tree=[],
        )
        processor._gitlab_webhook_client = client

        result = await processor.handle_event(payload, self._config())

        assert result.updated_raw_results == []
        assert [
            item["skill"]["skillMdPath"] for item in result.deleted_raw_results
        ] == ["skills/hello/SKILL.md"]

    async def test_nested_skill_md_added_rebuilds_parent(
        self, processor: SkillPushWebhookProcessor, payload: dict[str, Any]
    ) -> None:
        client = make_folder_client(
            payload["project"],
            compare_diffs(added=["skills/parent/child/SKILL.md"]),
            tree=["skills/parent/SKILL.md", "skills/parent/child/SKILL.md"],
        )
        processor._gitlab_webhook_client = client

        result = await processor.handle_event(payload, self._config())

        assert sorted(
            item["skill"]["skillMdPath"] for item in result.updated_raw_results
        ) == ["skills/parent/SKILL.md", "skills/parent/child/SKILL.md"]

    async def test_skill_md_edit_skips_owner_detection(
        self, processor: SkillPushWebhookProcessor, payload: dict[str, Any]
    ) -> None:
        client = make_folder_client(
            payload["project"],
            compare_diffs(modified=["skills/hello/SKILL.md"]),
            tree=["skills/hello/SKILL.md"],
        )
        processor._gitlab_webhook_client = client

        result = await processor.handle_event(payload, self._config())

        assert len(result.updated_raw_results) == 1
        assert client.tree_calls == [("skills/hello", "bbb222")]

    async def test_change_outside_skill_roots_lists_no_tree(
        self, processor: SkillPushWebhookProcessor, payload: dict[str, Any]
    ) -> None:
        client = make_folder_client(
            payload["project"],
            compare_diffs(modified=["README.md"]),
            tree=["README.md", "skills/hello/SKILL.md"],
        )
        processor._gitlab_webhook_client = client

        result = await processor.handle_event(payload, self._config())

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
        assert client.tree_calls == []

    async def test_oversized_skill_is_deleted(
        self, processor: SkillPushWebhookProcessor, payload: dict[str, Any]
    ) -> None:
        client = make_folder_client(
            payload["project"],
            compare_diffs(modified=["skills/hello/data.csv"]),
            tree=["skills/hello/SKILL.md", "skills/hello/data.csv"],
            contents={"skills/hello/data.csv": "x" * (1024 * 1024)},
        )
        processor._gitlab_webhook_client = client

        result = await processor.handle_event(payload, self._config())

        assert result.updated_raw_results == []
        assert [
            item["skill"]["skillMdPath"] for item in result.deleted_raw_results
        ] == ["skills/hello/SKILL.md"]
