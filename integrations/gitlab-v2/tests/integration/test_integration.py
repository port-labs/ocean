import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEventRawResults,
    WebhookEvent,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from integration import (
    GitlabIntegration,
    GitManipulationHandler,
    GitlabLiveEventsProcessorManager,
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
        headers={"x-gitlab-event": "Push Hook"},
        payload={"project": {"id": "123"}, "event_name": "push"},
    )


@pytest.fixture
def mock_webhook_results() -> WebhookEventRawResults:
    return WebhookEventRawResults(
        updated_raw_results=[{"id": "123", "name": "test-project"}],
        deleted_raw_results=[],
    )


@pytest.fixture
def mock_resource_config() -> MagicMock:
    config = MagicMock(spec=ResourceConfig)
    config.kind = "project"
    config.selector = MagicMock()
    config.selector.query = ""
    config.selector.include_languages = False
    return config


async def test_gitlab_integration_uses_gitmanipulation_handler(
    mock_context: MagicMock, mock_signal_handler: AsyncMock
) -> None:
    """Test that GitlabIntegration uses GitManipulationHandler as its EntityProcessorClass"""
    # Arrange & Act
    with patch("integration.signal_handler", mock_signal_handler):
        integration = GitlabIntegration(mock_context)

        # Assert
        assert integration.EntityProcessorClass == GitManipulationHandler


async def test_gitlab_webhook_manager_uses_gitmanipulation_handler(
    mock_context: MagicMock, mock_signal_handler: AsyncMock
) -> None:
    """Test that GitlabLiveEventsProcessorManager uses GitManipulationHandler as its EntityProcessorClass"""
    # Arrange & Act
    with patch("integration.signal_handler", mock_signal_handler):
        integration = GitlabIntegration(mock_context)
        manager = integration.context.app.webhook_manager

        # Assert
        assert isinstance(manager, GitlabLiveEventsProcessorManager)
        assert manager.EntityProcessorClass == GitManipulationHandler
