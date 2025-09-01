import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEventRawResults,
    WebhookEvent,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from integration import (
    GitHubIntegration,
    GitManipulationHandler,
    GitHubLiveEventsProcessorManager,
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
def mock_signal_handler() -> MagicMock:
    return MagicMock()


async def test_github_integration_uses_gitmanipulation_handler(
    mock_context: MagicMock, mock_signal_handler: AsyncMock
) -> None:
    """Test that GitHubIntegration uses GitManipulationHandler as its EntityProcessorClass"""
    # Arrange & Act
    with patch("integration.signal_handler", mock_signal_handler):
        integration = GitHubIntegration(mock_context)

        # Assert
        assert integration.EntityProcessorClass == GitManipulationHandler


async def test_github_webhook_manager_uses_gitmanipulation_handler(
    mock_context: MagicMock, mock_signal_handler: AsyncMock
) -> None:
    """Test that GitHubLiveEventsProcessorManager uses GitManipulationHandler as its EntityProcessorClass"""
    # Arrange & Act
    with patch("integration.signal_handler", mock_signal_handler):
        integration = GitHubIntegration(mock_context)
        manager = integration.context.app.webhook_manager

        # Assert
        assert isinstance(manager, GitHubLiveEventsProcessorManager)
        assert manager.EntityProcessorClass == GitManipulationHandler
