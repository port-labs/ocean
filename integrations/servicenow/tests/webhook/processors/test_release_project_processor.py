import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
    ResourceConfig,
    Selector,
)

from webhook.processors.release_project_processor import (
    ReleaseProjectWebhookProcessor,
)
from integration import ObjectKind
from tests.conftest import SAMPLE_RELEASE_PROJECT_DATA


@pytest.fixture
def resource_config() -> ResourceConfig:
    """Create a resource config fixture for release project."""
    return ResourceConfig(
        kind="release_project",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".sys_id",
                    title=".name",
                    blueprint='"servicenowReleaseProject"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def release_project_processor(
    mock_webhook_event: WebhookEvent,
) -> ReleaseProjectWebhookProcessor:
    """Create a release project webhook processor fixture."""
    return ReleaseProjectWebhookProcessor(event=mock_webhook_event)


@pytest.mark.asyncio
class TestReleaseProjectWebhookProcessor:
    """Test suite for ReleaseProjectWebhookProcessor."""

    async def test_get_matching_kinds(
        self, release_project_processor: ReleaseProjectWebhookProcessor
    ) -> None:
        """Test that get_matching_kinds returns the correct kind."""
        mock_event = MagicMock(spec=WebhookEvent)

        kinds = await release_project_processor.get_matching_kinds(mock_event)

        assert kinds == [ObjectKind.RELEASE_PROJECT]

    async def test_should_process_event_valid(
        self, release_project_processor: ReleaseProjectWebhookProcessor
    ) -> None:
        """Test that _should_process_event returns True for correct class name."""
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.payload = {
            "type": "release",
            "risk": "low",
            "sys_id": "test123",
        }

        result = release_project_processor._should_process_event(mock_event)

        assert result is True

    async def test_should_process_event_invalid(
        self, release_project_processor: ReleaseProjectWebhookProcessor
    ) -> None:
        """Test that _should_process_event returns False for incorrect class name."""
        mock_event = MagicMock(spec=WebhookEvent)
        mock_event.payload = {"sys_class_name": "incident", "sys_id": "test123"}

        result = release_project_processor._should_process_event(mock_event)

        assert result is False

    async def test_handle_event_found(
        self,
        release_project_processor: ReleaseProjectWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling an event when the record is found."""
        payload = {
            "sys_id": SAMPLE_RELEASE_PROJECT_DATA["sys_id"],
            "type": "release",
            "risk": "low",
        }

        mock_client = MagicMock()
        mock_client.get_record_by_sys_id = AsyncMock(
            return_value=SAMPLE_RELEASE_PROJECT_DATA
        )

        with patch(
            "webhook.processors.release_project_processor.initialize_webhook_client",
            return_value=mock_client,
        ):
            result = await release_project_processor.handle_event(
                payload, resource_config
            )

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == [SAMPLE_RELEASE_PROJECT_DATA]
            assert result.deleted_raw_results == []

    async def test_handle_event_deleted(
        self,
        release_project_processor: ReleaseProjectWebhookProcessor,
        resource_config: ResourceConfig,
    ) -> None:
        """Test handling an event when the record is not found."""
        payload = {
            "sys_id": "deleted_id",
            "type": "release",
            "risk": "low",
        }

        mock_client = MagicMock()
        mock_client.get_record_by_sys_id = AsyncMock(return_value=None)

        with patch(
            "webhook.processors.release_project_processor.initialize_webhook_client",
            return_value=mock_client,
        ):
            result = await release_project_processor.handle_event(
                payload, resource_config
            )

            assert isinstance(result, WebhookEventRawResults)
            assert result.updated_raw_results == []
            assert result.deleted_raw_results == [payload]
