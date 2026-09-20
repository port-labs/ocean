from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
