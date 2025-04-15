import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEventRawResults,
    WebhookEvent,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from integration import (
    BitbucketIntegration,
    GitManipulationHandler,
    BitbucketLiveEventsProcessorManager,
)


@pytest.fixture
def mock_context() -> MagicMock:
    context = MagicMock(spec=PortOceanContext)
    context.app = MagicMock()
    context.app.integration_router = MagicMock()
    context.config = MagicMock()
    context.config.max_event_processing_seconds = 60
    context.config.max_wait_seconds_before_shutdown = 30
    return context


@pytest.fixture
def mock_signal_handler() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_webhook_event() -> WebhookEvent:
    return WebhookEvent(
        trace_id="test-trace-id",
        headers={"x-event-key": "repo:push"},
        payload={"repository": {"uuid": "123"}, "push": {"changes": []}},
    )


@pytest.fixture
def mock_webhook_results() -> WebhookEventRawResults:
    return WebhookEventRawResults(
        updated_raw_results=[{"uuid": "123", "name": "test-repo"}],
        deleted_raw_results=[],
    )


@pytest.fixture
def mock_resource_config() -> MagicMock:
    config = MagicMock(spec=ResourceConfig)
    config.kind = "repository"
    config.selector = MagicMock()
    config.selector.query = ""
    return config


@pytest.mark.asyncio
async def test_bitbucket_integration_uses_gitmanipulation_handler(
    mock_context: MagicMock, mock_signal_handler: AsyncMock
) -> None:
    """Test that BitbucketIntegration uses GitManipulationHandler as its EntityProcessorClass"""
    # Arrange & Act

    with patch("integration.signal_handler", mock_signal_handler):
        integration = BitbucketIntegration(mock_context)

        # Assert
        assert integration.EntityProcessorClass == GitManipulationHandler


@pytest.mark.asyncio
async def test_bitbucket_webhook_manager_uses_gitmanipulation_handler(
    mock_context: MagicMock, mock_signal_handler: AsyncMock
) -> None:
    """Test that BitbucketLiveEventsProcessorManager uses GitManipulationHandler as its EntityProcessorClass"""
    # Arrange & Act
    with patch("integration.signal_handler", mock_signal_handler):
        integration = BitbucketIntegration(mock_context)
        manager = integration.context.app.webhook_manager

        # Assert
        assert isinstance(manager, BitbucketLiveEventsProcessorManager)
        assert manager.EntityProcessorClass == GitManipulationHandler
