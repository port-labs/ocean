"""Tests for Harbor webhook registry."""

from unittest.mock import MagicMock, patch

from harbor.webhook.registry import register_harbor_webhooks


class TestHarborWebhookRegistry:
    """Test Harbor webhook registry."""

    @patch("harbor.webhook.registry.ocean")
    def test_register_harbor_webhooks(self, mock_ocean: MagicMock) -> None:
        """Test webhook registration registers both processors."""
        register_harbor_webhooks(path="/test/webhook")

        # Verify both artifact and repository processors are registered
        assert mock_ocean.add_webhook_processor.call_count == 2
