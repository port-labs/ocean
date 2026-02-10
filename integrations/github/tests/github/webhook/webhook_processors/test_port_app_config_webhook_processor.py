import pytest
from typing import Any, Dict
from unittest.mock import AsyncMock

from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.context.ocean import ocean

from github.helpers.port_app_config import ORG_CONFIG_FILE, ORG_CONFIG_REPO
from github.webhook.webhook_processors.port_app_config_webhook_processor import (
    PortAppConfigWebhookProcessor,
)


def _build_dummy_resource_config() -> ResourceConfig:
    """Build a minimal valid ResourceConfig instance for tests."""
    entity_mapping = EntityMapping(
        identifier="id",
        title=None,
        icon=None,
        blueprint="githubRepository",
        team=None,
    )
    return ResourceConfig(
        kind="test",
        selector=Selector(query="true"),
        port=PortResourceConfig(entity=MappingsConfig(mappings=entity_mapping)),
    )


@pytest.fixture
def port_app_config_webhook_processor(
    mock_webhook_event: WebhookEvent,
) -> PortAppConfigWebhookProcessor:
    return PortAppConfigWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def payload() -> EventPayload:
    return {
        "ref": "refs/heads/main",
        "before": "abc123",
        "after": "def456",
        "commits": [],
        "repository": {"name": ORG_CONFIG_REPO, "default_branch": "main"},
        "organization": {"login": "test-org"},
    }


@pytest.mark.asyncio
class TestPortAppConfigWebhookProcessor:
    async def test_should_process_event_only_for_push_on_org_config_repo(
        self, port_app_config_webhook_processor: PortAppConfigWebhookProcessor
    ) -> None:
        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"ref": "refs/heads/main", "repository": {"name": ORG_CONFIG_REPO}},
            headers={"x-github-event": "push"},
        )

        assert (
            await port_app_config_webhook_processor._should_process_event(event) is True
        )

        # Wrong event type
        event.headers = {"x-github-event": "issues"}
        assert (
            await port_app_config_webhook_processor._should_process_event(event)
            is False
        )

        # Wrong repo
        event.headers = {"x-github-event": "push"}
        event.payload["repository"]["name"] = "some-other-repo"
        assert (
            await port_app_config_webhook_processor._should_process_event(event)
            is False
        )

        # Not a branch ref
        event.payload["repository"]["name"] = ORG_CONFIG_REPO
        event.payload["ref"] = "refs/tags/v1.0.0"
        assert (
            await port_app_config_webhook_processor._should_process_event(event)
            is False
        )

    async def test_validate_payload_valid(
        self,
        port_app_config_webhook_processor: PortAppConfigWebhookProcessor,
        payload: EventPayload,
    ) -> None:
        assert await port_app_config_webhook_processor.validate_payload(payload) is True

    async def test_validate_payload_invalid_missing_fields(
        self, port_app_config_webhook_processor: PortAppConfigWebhookProcessor
    ) -> None:
        # Missing required keys
        invalid_payload: EventPayload = {
            "ref": "refs/heads/main",
            "before": "abc123",
            # "after" missing
            "commits": [],
            "repository": {"name": ORG_CONFIG_REPO, "default_branch": "main"},
            "organization": {"login": "test-org"},
        }
        assert (
            await port_app_config_webhook_processor.validate_payload(invalid_payload)
            is False
        )

    @pytest.mark.asyncio
    async def test_handle_event_triggers_resync_when_config_changed_and_repo_managed(
        self,
        port_app_config_webhook_processor: PortAppConfigWebhookProcessor,
        payload: EventPayload,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Arrange: mock diff to include ORG_CONFIG_FILE
        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [
                {"filename": ORG_CONFIG_FILE, "status": "modified"},
            ]
        }

        monkeypatch.setattr(
            "github.webhook.webhook_processors.port_app_config_webhook_processor.RestFileExporter",
            lambda *_args, **_kwargs: mock_exporter,
        )

        # Arrange: integration is repo-managed
        async def mock_get_integration(*_: Any, **__: Any) -> Dict[str, Any]:
            return {"config": {"repoManagedMapping": True}}

        monkeypatch.setattr(
            ocean.port_client,
            "get_current_integration",
            AsyncMock(side_effect=mock_get_integration),
        )

        # Arrange: patch trigger_resync so we don't actually resync or require port_app_config
        called: Dict[str, bool] = {"resync_called": False}

        async def mock_trigger_resync(*_: Any, **__: Any) -> None:
            called["resync_called"] = True

        monkeypatch.setattr(
            "github.webhook.webhook_processors.port_app_config_webhook_processor.PortAppConfigWebhookProcessor.trigger_resync",
            mock_trigger_resync,
        )

        # Act
        result = await port_app_config_webhook_processor.handle_event(
            payload, _build_dummy_resource_config()
        )

        # Assert
        assert isinstance(result, WebhookEventRawResults)
        assert called["resync_called"] is True

    @pytest.mark.asyncio
    async def test_handle_event_no_resync_when_file_not_changed(
        self,
        port_app_config_webhook_processor: PortAppConfigWebhookProcessor,
        payload: EventPayload,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Arrange: diff does not include ORG_CONFIG_FILE
        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [
                {"filename": "README.md", "status": "modified"},
            ]
        }

        monkeypatch.setattr(
            "github.webhook.webhook_processors.port_app_config_webhook_processor.RestFileExporter",
            lambda *_args, **_kwargs: mock_exporter,
        )

        # Arrange: integration is repo-managed
        monkeypatch.setattr(
            ocean.port_client,
            "get_current_integration",
            AsyncMock(return_value={"config": {"repoManagedMapping": True}}),
        )

        # Patch trigger_resync
        called: Dict[str, bool] = {"resync_called": False}

        async def mock_trigger_resync(*_: Any, **__: Any) -> None:
            called["resync_called"] = True

        monkeypatch.setattr(
            "github.webhook.webhook_processors.port_app_config_webhook_processor.PortAppConfigWebhookProcessor.trigger_resync",
            mock_trigger_resync,
        )

        # Act
        result = await port_app_config_webhook_processor.handle_event(
            payload, _build_dummy_resource_config()
        )

        # Assert
        assert isinstance(result, WebhookEventRawResults)
        assert called["resync_called"] is False
