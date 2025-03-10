import pytest
import json
import hashlib
import hmac
from unittest.mock import AsyncMock, patch
from typing import Any, AsyncGenerator
from bitbucket_integration.webhook.webhook_client import BitbucketWebhookClient


def compute_signature(secret: str, payload: dict[str, Any]) -> str:
    """Compute the HMAC-SHA256 signature in the expected format."""
    payload_bytes = json.dumps(payload).encode("utf-8")
    return (
        "sha256="
        + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    )


@pytest.fixture
def webhook_client_with_secret() -> BitbucketWebhookClient:
    """Create a BitbucketWebhookClient with a secret."""
    return BitbucketWebhookClient(
        secret="test-secret",
        workspace="test-workspace",
        username="test-user",
        app_password="test-password",
    )


@pytest.fixture
def webhook_client_no_secret() -> BitbucketWebhookClient:
    """Create a BitbucketWebhookClient without a secret."""
    return BitbucketWebhookClient(
        workspace="test-workspace", username="test-user", app_password="test-password"
    )


class TestBitbucketWebhookClient:

    def test_init_with_secret(
        self, webhook_client_with_secret: BitbucketWebhookClient
    ) -> None:
        """Test initialization with a secret."""
        assert webhook_client_with_secret.secret == "test-secret"

    def test_init_without_secret(
        self, webhook_client_no_secret: BitbucketWebhookClient
    ) -> None:
        """Test initialization without a secret."""
        assert webhook_client_no_secret.secret is None

    def test_workspace_webhook_url(
        self, webhook_client_with_secret: BitbucketWebhookClient
    ) -> None:
        """Test that the workspace webhook URL is correctly formed."""
        expected = "workspaces/test-workspace/hooks"
        assert webhook_client_with_secret._workspace_webhook_url == expected

    @pytest.mark.asyncio
    async def test_authenticate_incoming_webhook_with_valid_signature(
        self, webhook_client_with_secret: BitbucketWebhookClient
    ) -> None:
        """Test webhook authentication with a valid signature."""
        payload = {"test": "data"}
        valid_signature = compute_signature(
            str(webhook_client_with_secret.secret), payload
        )
        headers = {"x-hub-signature": valid_signature}

        result = await webhook_client_with_secret.authenticate_incoming_webhook(
            payload, headers
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_authenticate_incoming_webhook_with_invalid_signature(
        self, webhook_client_with_secret: BitbucketWebhookClient
    ) -> None:
        """Test webhook authentication with an invalid signature."""
        payload = {"test": "data"}
        headers = {"x-hub-signature": "sha256=invalid"}

        result = await webhook_client_with_secret.authenticate_incoming_webhook(
            payload, headers
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_authenticate_incoming_webhook_without_signature(
        self, webhook_client_with_secret: BitbucketWebhookClient
    ) -> None:
        """Test webhook authentication when no signature is provided."""
        payload = {"test": "data"}
        headers: dict[str, Any] = {}

        result = await webhook_client_with_secret.authenticate_incoming_webhook(
            payload, headers
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_authenticate_incoming_webhook_no_secret(
        self, webhook_client_no_secret: BitbucketWebhookClient
    ) -> None:
        """Test webhook authentication when no secret is configured."""
        payload = {"test": "data"}
        headers: dict[str, Any] = {}

        result = await webhook_client_no_secret.authenticate_incoming_webhook(
            payload, headers
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_webhook_exist_not_found(
        self, webhook_client_with_secret: BitbucketWebhookClient
    ) -> None:
        """Test that _webhook_exist returns False when no matching webhook is found."""

        async def fake_paginated_response(
            api_url: str,
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield []  # Simulate an empty batch

        with patch.object(
            webhook_client_with_secret,
            "_send_paginated_api_request",
            new=fake_paginated_response,
        ):
            result = await webhook_client_with_secret._webhook_exist(
                "https://example.com/webhook"
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_webhook_exist_found(
        self, webhook_client_with_secret: BitbucketWebhookClient
    ) -> None:
        """Test that _webhook_exist returns True when a matching webhook is found."""

        async def fake_paginated_response(
            api_url: str,
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield [{"url": "https://example.com/integration/webhook", "id": "hook-123"}]

        with patch.object(
            webhook_client_with_secret,
            "_send_paginated_api_request",
            new=fake_paginated_response,
        ):
            result = await webhook_client_with_secret._webhook_exist(
                "https://example.com"
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_create_webhook_when_not_exist(
        self, webhook_client_with_secret: BitbucketWebhookClient
    ) -> None:
        """Test that create_webhook creates a new webhook when none exists."""
        # Simulate that no webhook exists.
        with patch.object(
            webhook_client_with_secret,
            "_webhook_exist",
            new=AsyncMock(return_value=False),
        ):
            # Patch _send_api_request to simulate a successful webhook creation.
            with patch.object(
                webhook_client_with_secret,
                "_send_api_request",
                new=AsyncMock(return_value={"id": "hook-123"}),
            ) as mock_send:
                await webhook_client_with_secret.create_webhook(
                    "https://example.com/webhook"
                )
                mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_webhook_when_already_exists(
        self, webhook_client_with_secret: BitbucketWebhookClient
    ) -> None:
        """Test that create_webhook does not create a webhook if one already exists."""
        # Simulate that the webhook already exists.
        with patch.object(
            webhook_client_with_secret,
            "_webhook_exist",
            new=AsyncMock(return_value=True),
        ):
            # Patch _send_api_request and verify it is not called.
            with patch.object(
                webhook_client_with_secret, "_send_api_request", new=AsyncMock()
            ) as mock_send:
                await webhook_client_with_secret.create_webhook(
                    "https://example.com/webhook"
                )
                mock_send.assert_not_called()
