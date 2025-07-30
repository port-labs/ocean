import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.context.ocean import PortOceanContext


@pytest.fixture
def mock_context():
    """Create a mock PortOceanContext for testing."""
    context = MagicMock(spec=PortOceanContext)
    context.ocean = MagicMock()
    return context


@pytest.fixture
def base_integration(mock_context):
    """Create a BaseIntegration instance for testing."""
    integration = BaseIntegration(mock_context)
    integration.event_strategy = {"start": []}
    integration.initialize_handlers = AsyncMock()
    integration.event_listener_factory = MagicMock()
    integration.event_listener_factory.create_event_listener = AsyncMock()
    return integration


class TestBaseIntegrationWebhooksOnlyFix:
    """Test the fix for WEBHOOKS_ONLY integration failure when webhook creation fails."""

    @pytest.mark.asyncio
    async def test_webhooks_only_integration_handles_start_event_failures_gracefully(
        self, base_integration, mock_context
    ):
        """
        Test that for WEBHOOKS_ONLY integrations, start event failures
        are handled gracefully and don't prevent integration startup.
        """
        # Mock ocean context for WEBHOOKS_ONLY
        mock_context.ocean.event_listener_type = "WEBHOOKS_ONLY"

        # Create a failing start event listener
        async def failing_start_listener():
            raise Exception("Webhook creation failed")

        base_integration.event_strategy = {"start": [failing_start_listener]}

        # Mock the event listener
        mock_event_listener = AsyncMock()
        base_integration.event_listener_factory.create_event_listener.return_value = (
            mock_event_listener
        )

        with patch("port_ocean.core.integrations.base.logger") as mock_logger:
            # Start the integration - this should not raise an exception
            await base_integration.start()

            # Verify the integration started successfully
            assert base_integration.started is True

            # Verify the event listener was started
            mock_event_listener.start.assert_called_once()

            # Give the async task time to complete
            await asyncio.sleep(0.1)

            # Verify warning was logged for WEBHOOKS_ONLY integration
            mock_logger.warning.assert_called_once()
            warning_call = mock_logger.warning.call_args[0][0]
            assert "Failed to execute start event listeners for WEBHOOKS_ONLY integration" in warning_call
            assert "The integration will continue to run and listen for webhook events" in warning_call
            assert "If you have manually created webhooks, this is expected" in warning_call

    @pytest.mark.asyncio
    async def test_non_webhooks_only_integration_still_logs_exceptions(
        self, base_integration, mock_context
    ):
        """
        Test that for non-WEBHOOKS_ONLY integrations, start event failures
        still log exceptions as before (maintains existing behavior).
        """
        # Mock ocean context for WEBHOOK (not WEBHOOKS_ONLY)
        mock_context.ocean.event_listener_type = "WEBHOOK"

        # Create a failing start event listener
        async def failing_start_listener():
            raise Exception("Webhook creation failed")

        base_integration.event_strategy = {"start": [failing_start_listener]}

        # Mock the event listener
        mock_event_listener = AsyncMock()
        base_integration.event_listener_factory.create_event_listener.return_value = (
            mock_event_listener
        )

        with patch("port_ocean.core.integrations.base.logger") as mock_logger:
            # Start the integration - this should not raise an exception
            await base_integration.start()

            # Verify the integration started successfully
            assert base_integration.started is True

            # Verify the event listener was started
            mock_event_listener.start.assert_called_once()

            # Give the async task time to complete
            await asyncio.sleep(0.1)

            # This SHOULD still use logger.exception for non-WEBHOOKS_ONLY integrations
            mock_logger.exception.assert_called_once()
            exception_call = mock_logger.exception.call_args[0][0]
            assert "Error in start event listeners" in exception_call

    @pytest.mark.asyncio
    async def test_once_event_listener_continues_to_work_normally(
        self, base_integration, mock_context
    ):
        """
        Test that ONCE event listener continues to work normally without being affected.
        """
        # Mock ocean context for ONCE
        mock_context.ocean.event_listener_type = "ONCE"

        # Create a normal start event listener
        async def normal_start_listener():
            pass

        base_integration.event_strategy = {"start": [normal_start_listener]}

        # Mock the event listener
        mock_event_listener = AsyncMock()
        base_integration.event_listener_factory.create_event_listener.return_value = (
            mock_event_listener
        )

        with patch("port_ocean.core.integrations.base.logger") as mock_logger:
            # Start the integration
            await base_integration.start()

            # Verify the integration started successfully
            assert base_integration.started is True

            # Verify the event listener was started
            mock_event_listener.start.assert_called_once()

            # Give the async task time to complete
            await asyncio.sleep(0.1)

            # No warnings or exceptions should be logged for successful start
            mock_logger.warning.assert_not_called()
            mock_logger.exception.assert_not_called()

    @pytest.mark.asyncio
    async def test_webhooks_only_with_successful_start_events(
        self, base_integration, mock_context
    ):
        """
        Test that WEBHOOKS_ONLY integrations work normally when start events succeed.
        """
        # Mock ocean context for WEBHOOKS_ONLY
        mock_context.ocean.event_listener_type = "WEBHOOKS_ONLY"

        # Create a successful start event listener
        async def successful_start_listener():
            pass

        base_integration.event_strategy = {"start": [successful_start_listener]}

        # Mock the event listener
        mock_event_listener = AsyncMock()
        base_integration.event_listener_factory.create_event_listener.return_value = (
            mock_event_listener
        )

        with patch("port_ocean.core.integrations.base.logger") as mock_logger:
            # Start the integration
            await base_integration.start()

            # Verify the integration started successfully
            assert base_integration.started is True

            # Verify the event listener was started
            mock_event_listener.start.assert_called_once()

            # Give the async task time to complete
            await asyncio.sleep(0.1)

            # No warnings or exceptions should be logged for successful start
            mock_logger.warning.assert_not_called()
            mock_logger.exception.assert_not_called()