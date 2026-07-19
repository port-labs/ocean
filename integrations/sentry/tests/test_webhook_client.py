"""Unit tests for the Sentry Webhook Client."""

from unittest.mock import patch

import pytest
from webhook_processors.webhook_client import SentryWebhookClient


pytestmark = pytest.mark.asyncio


@pytest.fixture
def sentry_webhook_client() -> SentryWebhookClient:
    """Provides a SentryWebhookClient instance for testing."""
    return SentryWebhookClient(
        sentry_base_url="https://sentry.io",
        auth_token="test-token",
        sentry_organization="test-org",
    )


class TestEnsureSentryApps:
    """Tests for the ensure_sentry_apps method."""

    async def test_ensure_sentry_apps_exists(
        self, sentry_webhook_client: SentryWebhookClient
    ) -> None:
        """Tests ensure_sentry_apps finds existing app."""
        expected_url = "https://example.com/integration/webhook"
        mock_apps = [
            {"webhookUrl": "https://other.com"},
            {"webhookUrl": expected_url},
        ]

        with patch.object(
            sentry_webhook_client,
            "_get_sentry_apps",
            return_value=mock_apps,
        ) as mock_get_apps:
            await sentry_webhook_client.ensure_sentry_apps("https://example.com")

            mock_get_apps.assert_awaited_once()

    async def test_ensure_sentry_apps_missing(
        self, sentry_webhook_client: SentryWebhookClient
    ) -> None:
        """Tests ensure_sentry_apps handles missing app."""
        mock_apps = [{"webhookUrl": "https://other.com"}]

        with (
            patch.object(
                sentry_webhook_client,
                "_get_sentry_apps",
                return_value=mock_apps,
            ) as mock_get_apps,
            patch("webhook_processors.webhook_client.logger") as mock_logger,
        ):
            await sentry_webhook_client.ensure_sentry_apps("https://example.com")

            mock_get_apps.assert_awaited_once()
            mock_logger.warning.assert_called_with(
                "Sentry app with webhook URL https://example.com/integration/webhook does not exist. Skipping webhook creation..."
            )
