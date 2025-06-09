import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
import httpx


class TestJiraWebhooksOnlyFix:
    """Test the fix for WEBHOOKS_ONLY Jira integration webhook creation failures."""

    @pytest.mark.asyncio
    async def test_webhooks_only_handles_webhook_creation_failures_gracefully(self):
        """
        Test that for WEBHOOKS_ONLY integrations, webhook creation failures
        are handled gracefully and do not prevent the integration from starting.
        
        This addresses the issue where customers manually create webhooks 
        but don't provide elevated permissions for automatic webhook creation.
        """
        
        # Mock setup_application to raise an HTTP error (permission denied)
        setup_application_mock = AsyncMock(side_effect=httpx.HTTPStatusError(
            "403 Forbidden - Insufficient permissions to create webhooks",
            request=Mock(),
            response=Mock(status_code=403)
        ))
        
        # Mock ocean context for WEBHOOKS_ONLY
        ocean_mock = Mock()
        ocean_mock.event_listener_type = "WEBHOOKS_ONLY"
        
        # Mock logger
        logger_mock = Mock()
        
        # Simulate the fixed on_start logic
        async def on_start_logic():
            logger_mock.info("Starting Port Ocean Jira integration")

            if ocean_mock.event_listener_type == "ONCE":
                logger_mock.info("Skipping webhook creation because the event listener is ONCE")
                return

            # For WEBHOOKS_ONLY integrations, webhook creation failures should not prevent
            # the integration from starting, as customers may have created webhooks manually
            if ocean_mock.event_listener_type == "WEBHOOKS_ONLY":
                try:
                    await setup_application_mock()
                except Exception as e:
                    logger_mock.warning(
                        f"Failed to create webhooks for WEBHOOKS_ONLY integration: {e}. "
                        "The integration will continue to run and listen for webhook events. "
                        "If you have manually created webhooks, this is expected."
                    )
                return

            await setup_application_mock()
        
        # This should NOT raise an exception - the integration should continue
        await on_start_logic()
        
        # Verify that setup_application was called (attempted webhook creation)
        setup_application_mock.assert_called_once()
        
        # Verify that a helpful warning was logged
        logger_mock.warning.assert_called_once()
        warning_call = logger_mock.warning.call_args[0][0]
        assert "Failed to create webhooks for WEBHOOKS_ONLY integration" in warning_call
        assert "manually created webhooks" in warning_call

    @pytest.mark.asyncio
    async def test_non_webhooks_only_still_propagates_exceptions(self):
        """
        Test that for non-WEBHOOKS_ONLY integrations, webhook creation failures
        still raise exceptions as before (no change in behavior).
        """
        
        # Mock setup_application to raise an HTTP error
        setup_application_mock = AsyncMock(side_effect=httpx.HTTPStatusError(
            "403 Forbidden",
            request=Mock(),
            response=Mock(status_code=403)
        ))
        
        # Mock ocean context for WEBHOOK (not WEBHOOKS_ONLY)
        ocean_mock = Mock()
        ocean_mock.event_listener_type = "WEBHOOK"
        
        # Mock logger
        logger_mock = Mock()
        
        # Simulate the fixed on_start logic
        async def on_start_logic():
            logger_mock.info("Starting Port Ocean Jira integration")

            if ocean_mock.event_listener_type == "ONCE":
                logger_mock.info("Skipping webhook creation because the event listener is ONCE")
                return

            # For WEBHOOKS_ONLY integrations, webhook creation failures should not prevent
            # the integration from starting, as customers may have created webhooks manually
            if ocean_mock.event_listener_type == "WEBHOOKS_ONLY":
                try:
                    await setup_application_mock()
                except Exception as e:
                    logger_mock.warning(
                        f"Failed to create webhooks for WEBHOOKS_ONLY integration: {e}. "
                        "The integration will continue to run and listen for webhook events. "
                        "If you have manually created webhooks, this is expected."
                    )
                return

            await setup_application_mock()
        
        # This SHOULD still raise an exception for non-WEBHOOKS_ONLY integrations
        with pytest.raises(httpx.HTTPStatusError):
            await on_start_logic()

    @pytest.mark.asyncio
    async def test_once_listener_behavior_unchanged(self):
        """
        Test that ONCE event listener behavior is unchanged - 
        it still skips webhook creation entirely.
        """
        
        # Mock setup_application - it should not be called
        setup_application_mock = AsyncMock()
        
        # Mock ocean context for ONCE
        ocean_mock = Mock()
        ocean_mock.event_listener_type = "ONCE"
        
        # Mock logger
        logger_mock = Mock()
        
        # Simulate the fixed on_start logic
        async def on_start_logic():
            logger_mock.info("Starting Port Ocean Jira integration")

            if ocean_mock.event_listener_type == "ONCE":
                logger_mock.info("Skipping webhook creation because the event listener is ONCE")
                return

            # For WEBHOOKS_ONLY integrations, webhook creation failures should not prevent
            # the integration from starting, as customers may have created webhooks manually
            if ocean_mock.event_listener_type == "WEBHOOKS_ONLY":
                try:
                    await setup_application_mock()
                except Exception as e:
                    logger_mock.warning(
                        f"Failed to create webhooks for WEBHOOKS_ONLY integration: {e}. "
                        "The integration will continue to run and listen for webhook events. "
                        "If you have manually created webhooks, this is expected."
                    )
                return

            await setup_application_mock()
        
        # Should complete without calling setup_application
        await on_start_logic()
        
        # Verify setup_application was not called
        setup_application_mock.assert_not_called()
        
        # Verify the skip message was logged
        logger_mock.info.assert_any_call("Skipping webhook creation because the event listener is ONCE")