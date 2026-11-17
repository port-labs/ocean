"""Tests for webhook_setup.py error handling."""

import pytest
import httpx
from unittest.mock import AsyncMock, Mock, patch

from plain.webhook_setup import register_webhook_target


@pytest.mark.asyncio
async def test_register_webhook_logs_warning_on_request_error() -> None:
    """
    When Plain API cannot be reached (httpx.RequestError), webhook registration
    should log a clear warning but not crash.
    """
    # Mock ocean config
    mock_ocean = Mock()
    mock_ocean.app.base_url = "https://app.example.com"

    # Mock PlainClient to raise RequestError
    mock_client = Mock()
    mock_client.ensure_webhook_target = AsyncMock(
        side_effect=httpx.ConnectError("Connection refused")
    )

    with patch("plain.webhook_setup.ocean", mock_ocean):
        with patch("plain.webhook_setup.PlainClient", return_value=mock_client):
            with patch("plain.webhook_setup.logger") as mock_logger:
                # Should not raise
                await register_webhook_target()

                # Should have logged warning
                mock_logger.warning.assert_called_once()
                warning_msg = str(mock_logger.warning.call_args[0])
                assert "Could not reach Plain API" in warning_msg
                assert "webhook" in warning_msg.lower()


@pytest.mark.asyncio
async def test_register_webhook_skips_when_base_url_not_set() -> None:
    """When OCEAN__BASE_URL is not set, webhook registration should be skipped."""
    mock_ocean = Mock()
    mock_ocean.app.base_url = None

    with patch("plain.webhook_setup.ocean", mock_ocean):
        with patch("plain.webhook_setup.logger") as mock_logger:
            await register_webhook_target()

            # Should have logged that it's skipping
            mock_logger.warning.assert_called_once()
            warning_msg = str(mock_logger.warning.call_args[0])
            assert "Skipping" in warning_msg
            assert "OCEAN__BASE_URL" in warning_msg


@pytest.mark.asyncio
async def test_register_webhook_succeeds_without_logging() -> None:
    """When webhook registration succeeds, no warnings should be logged."""
    mock_ocean = Mock()
    mock_ocean.app.base_url = "https://app.example.com"

    mock_client = Mock()
    mock_client.ensure_webhook_target = AsyncMock()

    with patch("plain.webhook_setup.ocean", mock_ocean):
        with patch("plain.webhook_setup.PlainClient", return_value=mock_client):
            with patch("plain.webhook_setup.logger") as mock_logger:
                await register_webhook_target()

                # Should not have logged any warnings
                mock_logger.warning.assert_not_called()
