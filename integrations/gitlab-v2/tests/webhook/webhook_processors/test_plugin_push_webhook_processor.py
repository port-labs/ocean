from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from gitlab.helpers.skill_plugin import DEFAULT_PLUGIN_PROVIDERS
from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors.plugin_push_webhook_processor import (
    PluginPushWebhookProcessor,
)
from gitlab.webhook.webhook_processors.push_constants import DELETED_COMMIT_SHA
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


def make_plugin_resource_config(
    providers: list[str] | None = None,
    repos: list[str] | None = None,
) -> MagicMock:
    config = MagicMock()
    config.selector.providers = providers or list(DEFAULT_PLUGIN_PROVIDERS)
    config.selector.repos = repos or []
    config.kind = "plugin"
    return config


@pytest.mark.asyncio
class TestPluginPushWebhookProcessor:
    @pytest.fixture
    def mock_event(self) -> WebhookEvent:
        return WebhookEvent(
            trace_id="test-trace-id",
            headers={"x-gitlab-event": "Push Hook"},
            payload={},
        )

    @pytest.fixture
    def processor(self, mock_event: WebhookEvent) -> PluginPushWebhookProcessor:
        return PluginPushWebhookProcessor(event=mock_event)

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
                    "added": [".cursor-plugin/plugin.json"],
                    "modified": [],
                    "removed": [],
                }
            ],
        }

    async def test_get_matching_kinds(
        self, processor: PluginPushWebhookProcessor, mock_event: WebhookEvent
    ) -> None:
        assert await processor.get_matching_kinds(mock_event) == [ObjectKind.PLUGIN]

    async def test_skips_non_default_branch(
        self,
        processor: PluginPushWebhookProcessor,
        base_payload: dict[str, Any],
    ) -> None:
        payload = {**base_payload, "ref": "refs/heads/feature"}
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(payload, make_plugin_resource_config())

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_skips_branch_delete(
        self,
        processor: PluginPushWebhookProcessor,
        base_payload: dict[str, Any],
    ) -> None:
        payload = {**base_payload, "after": DELETED_COMMIT_SHA}
        processor._gitlab_webhook_client = MagicMock()

        result = await processor.handle_event(payload, make_plugin_resource_config())

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_rebuild_plugin_on_manifest_change(
        self,
        processor: PluginPushWebhookProcessor,
        base_payload: dict[str, Any],
    ) -> None:
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client._process_file_batch = AsyncMock(
            return_value=[
                {
                    "path": ".cursor-plugin/plugin.json",
                    "content": {"name": "cursor-plugin"},
                    "ref": "bbb222",
                }
            ]
        )
        setattr(
            processor,
            "_list_directory_plugin_paths",
            AsyncMock(return_value=set()),
        )

        result = await processor.handle_event(
            base_payload, make_plugin_resource_config()
        )

        assert len(result.updated_raw_results) == 1
        plugin = result.updated_raw_results[0]["plugin"]
        assert plugin["supports"]["cursor"] is True
        assert result.deleted_raw_results == []

    async def test_delete_when_manifests_gone(
        self,
        processor: PluginPushWebhookProcessor,
        base_payload: dict[str, Any],
    ) -> None:
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client._process_file_batch = AsyncMock(
            return_value=[]
        )
        setattr(
            processor,
            "_list_directory_plugin_paths",
            AsyncMock(return_value=set()),
        )

        result = await processor.handle_event(
            base_payload, make_plugin_resource_config()
        )

        assert result.updated_raw_results == []
        assert len(result.deleted_raw_results) == 1
        assert result.deleted_raw_results[0]["plugin"]["name"] == "project"
        assert result.deleted_raw_results[0]["__branch"] == "main"

    async def test_truncated_push_uses_compare_api(
        self,
        processor: PluginPushWebhookProcessor,
        base_payload: dict[str, Any],
    ) -> None:
        payload = {
            **base_payload,
            "total_commits_count": 4,
            "commits": [{"added": ["README.md"], "modified": [], "removed": []}],
        }
        processor._gitlab_webhook_client = MagicMock()
        processor._gitlab_webhook_client.compare_repository = AsyncMock(
            return_value={
                "diffs": [
                    {
                        "new_path": ".cursor-plugin/plugin.json",
                        "old_path": ".cursor-plugin/plugin.json",
                        "new_file": True,
                        "deleted_file": False,
                    }
                ]
            }
        )
        processor._gitlab_webhook_client._process_file_batch = AsyncMock(
            return_value=[
                {
                    "path": ".cursor-plugin/plugin.json",
                    "content": {"name": "cursor-plugin"},
                    "ref": "bbb222",
                }
            ]
        )
        setattr(
            processor,
            "_list_directory_plugin_paths",
            AsyncMock(return_value=set()),
        )

        result = await processor.handle_event(payload, make_plugin_resource_config())

        processor._gitlab_webhook_client.compare_repository.assert_awaited_once_with(
            "group/project", "aaa111", "bbb222"
        )
        assert len(result.updated_raw_results) == 1
