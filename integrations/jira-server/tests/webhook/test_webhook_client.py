import pytest
from unittest.mock import AsyncMock, patch
from jira_server.webhook_processors.webhook_client import JiraWebhookClient


@pytest.fixture
def webhook_client() -> JiraWebhookClient:
    """Create a JiraWebhookClient with a secret."""
    return JiraWebhookClient(
        server_url="https://jira.example.com",
        username="test-user",
        password="test-password",
    )


class TestJiraWebhookClient:

    @pytest.mark.asyncio
    async def test_webhook_exist_not_found(
        self, webhook_client: JiraWebhookClient
    ) -> None:
        """Test that _webhook_exist returns False when no matching webhook is found."""

        with patch.object(
            webhook_client,
            "_send_api_request",
            new=AsyncMock(return_value=[]),
        ):
            result = await webhook_client._webhook_exist("https://example.com/webhook")
            assert result is False

    @pytest.mark.asyncio
    async def test_webhook_exist_found(self, webhook_client: JiraWebhookClient) -> None:
        """Test that _webhook_exist returns True when a matching webhook is found."""

        with patch.object(
            webhook_client,
            "_send_api_request",
            new=AsyncMock(
                return_value=[{"url": "https://example.com/webhook", "id": 123}]
            ),
        ):
            result = await webhook_client._webhook_exist("https://example.com/webhook")
            assert result is True

    @pytest.mark.asyncio
    async def test_create_webhook_when_not_exist(
        self, webhook_client: JiraWebhookClient
    ) -> None:
        """Test that create_webhook creates a new webhook when none exists."""
        # Simulate that no webhook exists.
        with patch.object(
            webhook_client,
            "_webhook_exist",
            new=AsyncMock(return_value=False),
        ):
            # Patch _send_api_request to simulate a successful webhook creation.
            with patch.object(
                webhook_client,
                "_send_api_request",
                new=AsyncMock(return_value={"id": 123}),
            ) as mock_send:
                await webhook_client.create_webhook("https://example.com")
                mock_send.assert_called_once()
                # Verify the payload structure
                call_args = mock_send.call_args
                assert call_args[0][0] == "POST"
                assert "json" in call_args[1]
                payload = call_args[1]["json"]
                assert payload["url"] == "https://example.com/integration/webhook"
                assert payload["name"] == "Port Ocean Jira Integration"
                assert payload["active"] == "true"

    @pytest.mark.asyncio
    async def test_create_webhook_when_already_exists(
        self, webhook_client: JiraWebhookClient
    ) -> None:
        """Test that create_webhook does not create a webhook if one already exists."""
        # Simulate that the webhook already exists.
        with patch.object(
            webhook_client,
            "_webhook_exist",
            new=AsyncMock(return_value=True),
        ):
            # Patch _send_api_request and verify it is not called.
            with patch.object(
                webhook_client, "_send_api_request", new=AsyncMock()
            ) as mock_send:
                await webhook_client.create_webhook("https://example.com")
                mock_send.assert_not_called()
