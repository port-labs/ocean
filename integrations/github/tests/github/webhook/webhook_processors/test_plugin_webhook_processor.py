import json
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic.v1 import ValidationError

from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.plugin_webhook_processor import (
    PluginWebhookProcessor,
)
from integration import (
    GithubPluginResourceConfig,
    GithubPluginSelector,
    RepositoryBranchMapping,
    RepositorySourceModel,
)
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


def _plugin_resource_config(
    paths: list[RepositorySourceModel],
) -> GithubPluginResourceConfig:
    return GithubPluginResourceConfig(
        kind=ObjectKind.PLUGIN,
        selector=GithubPluginSelector(query="true", paths=paths),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".metadata.path",
                    title=".metadata.name",
                    blueprint='"githubPlugin"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def plugin_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> PluginWebhookProcessor:
    return PluginWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def payload() -> EventPayload:
    return {
        "ref": "refs/heads/main",
        "before": "abc123",
        "after": "def456",
        "repository": {
            "name": "test-repo",
            "default_branch": "main",
            "archived": True,
        },
        "organization": {"login": "test-org"},
    }


@pytest.mark.asyncio
async def test_handle_event_skips_archived_implicit_repository(
    plugin_webhook_processor: PluginWebhookProcessor,
    payload: EventPayload,
) -> None:
    resource_config = _plugin_resource_config(
        [RepositorySourceModel(organization="test-org", excludeArchived=True)]
    )

    with patch(
        "github.webhook.webhook_processors.plugin_webhook_processor.create_github_client_for_org",
        new_callable=AsyncMock,
    ) as mock_create_client:
        result = await plugin_webhook_processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []
    mock_create_client.assert_not_called()


@pytest.mark.asyncio
async def test_handle_event_keeps_archived_explicit_repository(
    plugin_webhook_processor: PluginWebhookProcessor,
    payload: EventPayload,
) -> None:
    resource_config = _plugin_resource_config(
        [
            RepositorySourceModel(
                organization="test-org",
                repos=[RepositoryBranchMapping(name="test-repo", branch="main")],
                excludeArchived=True,
            )
        ]
    )

    mock_file_exporter = MagicMock()
    mock_file_exporter.fetch_commit_diff = AsyncMock(return_value={"files": []})

    with (
        patch(
            "github.webhook.webhook_processors.plugin_webhook_processor.create_github_client_for_org",
            new_callable=AsyncMock,
        ) as mock_create_client,
        patch(
            "github.webhook.webhook_processors.plugin_webhook_processor.RestFileExporter",
            return_value=mock_file_exporter,
        ),
    ):
        result = await plugin_webhook_processor.handle_event(payload, resource_config)

    assert isinstance(result, WebhookEventRawResults)
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []
    mock_create_client.assert_awaited_once_with("test-org")


FRONTEND = "plugins/frontend-toolkit/.claude-plugin/plugin.json"
QUALITY = "plugins/code-quality-toolkit/.cursor-plugin/plugin.json"


async def _handle(
    processor: PluginWebhookProcessor,
    payload: EventPayload,
    changed: list[dict[str, str]],
    tree: list[str],
    *,
    old_tree: Optional[list[str]] = None,
    truncated: frozenset[str] = frozenset(),
    names: Optional[dict[str, str]] = None,
) -> tuple[WebhookEventRawResults, MagicMock]:
    """Run handle_event for an explicit repo with a mocked diff and git trees.

    `tree` is the tree after the push (branch "main"), `old_tree` the one before
    it (ref "abc123", defaults to `tree`). `truncated` lists the refs GitHub
    truncates. `names` overrides a manifest's `name` (default: its folder name).
    """
    trees = {"main": tree, "abc123": tree if old_tree is None else old_tree}
    file_exporter = MagicMock()
    file_exporter.fetch_commit_diff = AsyncMock(return_value={"files": changed})
    file_exporter.get_tree_recursive = AsyncMock(
        side_effect=lambda _org, _repo, ref: (
            [{"type": "blob", "path": path} for path in trees[ref]],
            ref in truncated,
        )
    )
    file_exporter.get_resource = AsyncMock(
        side_effect=lambda options: {
            "content": json.dumps(
                {
                    "name": (names or {}).get(
                        options["file_path"], options["file_path"].split("/")[1]
                    )
                }
            )
        }
    )
    config = _plugin_resource_config(
        [
            RepositorySourceModel(
                organization="test-org",
                repos=[RepositoryBranchMapping(name="test-repo", branch="main")],
            )
        ]
    )
    with (
        patch(
            "github.webhook.webhook_processors.plugin_webhook_processor.create_github_client_for_org",
            new_callable=AsyncMock,
        ),
        patch(
            "github.webhook.webhook_processors.plugin_webhook_processor.RestFileExporter",
            return_value=file_exporter,
        ),
        patch(
            "github.core.exporters.plugin_exporter.core.RestFileExporter",
            return_value=file_exporter,
        ),
    ):
        return await processor.handle_event(payload, config), file_exporter


@pytest.mark.asyncio
async def test_handle_event_updates_only_the_changed_plugin_root(
    plugin_webhook_processor: PluginWebhookProcessor, payload: EventPayload
) -> None:
    result, _ = await _handle(
        plugin_webhook_processor,
        payload,
        [{"filename": FRONTEND, "status": "modified"}],
        [FRONTEND, QUALITY],
    )

    assert result.deleted_raw_results == []
    [item] = result.updated_raw_results
    assert item["plugin"]["path"] == "plugins/frontend-toolkit"
    assert item["plugin"]["name"] == "frontend-toolkit"


@pytest.mark.asyncio
async def test_handle_event_deletes_only_the_removed_plugin_root(
    plugin_webhook_processor: PluginWebhookProcessor, payload: EventPayload
) -> None:
    result, file_exporter = await _handle(
        plugin_webhook_processor,
        payload,
        [{"filename": FRONTEND, "status": "removed"}],
        [QUALITY],
        old_tree=[FRONTEND, QUALITY],
        # The manifest name differs from the folder name: a mapping identifier
        # built on `.plugin.name` must resolve to the same entity as before.
        names={FRONTEND: "frontend"},
    )

    assert result.updated_raw_results == []
    [item] = result.deleted_raw_results
    assert item["plugin"]["path"] == "plugins/frontend-toolkit"
    assert item["plugin"]["name"] == "frontend"
    assert item["plugin"]["supports"]["claude"] is True
    assert item["__branch"] == "main"
    # The removed manifest is read from the previous commit.
    [read] = [c.args[0] for c in file_exporter.get_resource.await_args_list]
    assert (read["file_path"], read["branch"]) == (FRONTEND, "abc123")


@pytest.mark.asyncio
async def test_handle_event_skips_delete_of_a_root_that_never_existed(
    plugin_webhook_processor: PluginWebhookProcessor, payload: EventPayload
) -> None:
    result, _ = await _handle(
        plugin_webhook_processor,
        payload,
        [{"filename": ".claude-plugin/marketplace.json", "status": "removed"}],
        [QUALITY],
        old_tree=[".claude-plugin/marketplace.json", QUALITY],
    )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_skips_everything_when_the_tree_is_truncated(
    plugin_webhook_processor: PluginWebhookProcessor, payload: EventPayload
) -> None:
    """A partial tree can neither confirm a removal nor a provider's absence."""
    result, file_exporter = await _handle(
        plugin_webhook_processor,
        payload,
        [{"filename": FRONTEND, "status": "modified"}],
        [QUALITY],
        truncated=frozenset({"main"}),
    )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []
    file_exporter.get_resource.assert_not_called()


@pytest.mark.asyncio
async def test_handle_event_skips_deletes_when_the_previous_tree_is_truncated(
    plugin_webhook_processor: PluginWebhookProcessor, payload: EventPayload
) -> None:
    result, _ = await _handle(
        plugin_webhook_processor,
        payload,
        [{"filename": FRONTEND, "status": "removed"}],
        [QUALITY],
        old_tree=[FRONTEND, QUALITY],
        truncated=frozenset({"abc123"}),
    )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_handle_event_ignores_non_marker_files(
    plugin_webhook_processor: PluginWebhookProcessor, payload: EventPayload
) -> None:
    result, file_exporter = await _handle(
        plugin_webhook_processor,
        payload,
        [{"filename": "plugins/frontend-toolkit/skills/x/SKILL.md"}],
        [FRONTEND],
    )

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []
    file_exporter.get_tree_recursive.assert_not_called()


@pytest.mark.parametrize(
    "value,error",
    [(0, True), (-1, True), (2, False), (None, False)],
)
def test_plugin_selector_max_depth_validation(value: Any, error: bool) -> None:
    data = {"query": "true", "maxDepth": value}
    if error:
        with pytest.raises(
            ValidationError, match="maxDepth must be greater than or equal to 1"
        ):
            GithubPluginSelector.parse_obj(data)
    else:
        assert GithubPluginSelector.parse_obj(data).max_depth == value
