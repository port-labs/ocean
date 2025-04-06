import pytest
from unittest.mock import AsyncMock, patch
from bitbucket_cloud.webhook_processors.webhook_client import BitbucketWebhookClient
from bitbucket_cloud.base_client import BitbucketBaseClient


@pytest.fixture
def webhook_client_with_secret() -> BitbucketWebhookClient:
    """Create a BitbucketWebhookClient with a secret."""
    base_client = BitbucketBaseClient(
        workspace="test-workspace",
        host="https://api.bitbucket.org/2.0",
        username="test-user",
        app_password="test-password",
    )
    return BitbucketWebhookClient(base_client=base_client, secret="test-secret")


@pytest.fixture
def webhook_client_no_secret() -> BitbucketWebhookClient:
    """Create a BitbucketWebhookClient without a secret."""
    base_client = BitbucketBaseClient(
        workspace="test-workspace",
        host="https://api.bitbucket.org/2.0",
        username="test-user",
        app_password="test-password",
    )
    return BitbucketWebhookClient(base_client=base_client)


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
        expected = "https://api.bitbucket.org/2.0/workspaces/test-workspace/hooks"
        assert webhook_client_with_secret._workspace_webhook_url == expected

    @pytest.mark.asyncio
    async def test_webhook_exist(
        self, webhook_client_with_secret: BitbucketWebhookClient
    ) -> None:
        """Test that _webhook_exist returns True when a webhook exists."""
        # Mock the _send_paginated_api_request method to return a webhook with the specified URL.
        async def mock_send_paginated_api_request(*args, **kwargs):
            yield [{"url": "https://example.com/integration/webhook", "description": "Port Bitbucket Integration"}]
            
        with patch.object(
            webhook_client_with_secret,
            "_send_paginated_api_request",
            new=mock_send_paginated_api_request,
        ):
            assert await webhook_client_with_secret._webhook_exist(
                "https://example.com/integration/webhook"
            )

    @pytest.mark.asyncio
    async def test_webhook_not_exist(
        self, webhook_client_with_secret: BitbucketWebhookClient
    ) -> None:
        """Test that _webhook_exist returns False when a webhook doesn't exist."""
        # Mock the _send_paginated_api_request method to return an empty list.
        async def mock_send_paginated_api_request(*args, **kwargs):
            yield []
            
        with patch.object(
            webhook_client_with_secret,
            "_send_paginated_api_request",
            new=mock_send_paginated_api_request,
        ):
            assert not await webhook_client_with_secret._webhook_exist(
                "https://example.com/integration/webhook"
            )

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
            # Patch base_client.send_api_request to simulate a successful webhook creation.
            with patch.object(
                webhook_client_with_secret.base_client,
                "send_api_request",
                new=AsyncMock(return_value={"id": "hook-123"}),
            ) as mock_send:
                await webhook_client_with_secret.create_webhook("https://example.com")
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
            # Patch send_api_request and verify it is not called.
            with patch.object(
                webhook_client_with_secret.base_client,
                "send_api_request",
                new=AsyncMock(),
            ) as mock_send:
                await webhook_client_with_secret.create_webhook("https://example.com")
                mock_send.assert_not_called()
