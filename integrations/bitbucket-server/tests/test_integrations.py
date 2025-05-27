from unittest.mock import MagicMock

import pytest
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)

from integration import BitbucketAppConfig, BitbucketIntegration


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
def mock_webhook_event() -> WebhookEvent:
    return WebhookEvent(
        trace_id="test-trace-id",
        headers={"x-event-key": "repo:refs_changed"},
        payload={"repository": {"id": 123}, "changes": []},
    )


@pytest.fixture
def mock_webhook_results() -> WebhookEventRawResults:
    return WebhookEventRawResults(
        updated_raw_results=[{"id": 123, "name": "test-repo"}],
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
async def test_bitbucket_integration_initialization(mock_context: MagicMock) -> None:
    """Test that BitbucketIntegration initializes correctly"""
    # Arrange & Act
    integration = BitbucketIntegration(mock_context)

    # Assert
    assert integration is not None
    assert integration.context == mock_context
    assert isinstance(
        integration.AppConfigHandlerClass.CONFIG_CLASS, type(BitbucketAppConfig)
    )


@pytest.mark.asyncio
async def test_bitbucket_integration_config_validation(mock_context: MagicMock) -> None:
    """Test that BitbucketIntegration validates config correctly"""
    # Arrange
    BitbucketIntegration(mock_context)
    config = BitbucketAppConfig(resources=[])

    # Act & Assert
    assert isinstance(config, BitbucketAppConfig)
    assert isinstance(config.resources, list)
    assert len(config.resources) == 0
