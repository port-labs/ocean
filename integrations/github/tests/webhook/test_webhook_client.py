import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from typing import Any, Dict, List, AsyncGenerator
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.webhook.webhook_client import GithubWebhookClient


@pytest.mark.asyncio
class TestGithubWebhookClient:
    async def test_get_existing_webhook_found(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Mock webhook data
        webhooks = [
            {
                "id": "hook1",
                "config": {
                    "url": "https://example.com/integration/webhook",
                    "content_type": "json",
                },
            },
            {
                "id": "hook2",
                "config": {
                    "url": "https://other-url.com/webhook",
                    "content_type": "json",
                },
            },
        ]

        # Create async generator to mock paginated response
        async def mock_paginated_generator() -> (
            AsyncGenerator[List[Dict[str, Any]], None]
        ):
            yield webhooks

        with patch.object(
            client, "send_paginated_request", return_value=mock_paginated_generator()
        ):
            result = await client._get_existing_webhook(
                "https://example.com/integration/webhook"
            )

            assert result is not None
            assert result["id"] == "hook1"
            assert result["config"]["url"] == "https://example.com/integration/webhook"

    async def test_get_existing_webhook_not_found(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Mock webhook data with no matching URL
        webhooks = [
            {
                "id": "hook1",
                "config": {
                    "url": "https://different-url.com/webhook",
                    "content_type": "json",
                },
            },
            {
                "id": "hook2",
                "config": {
                    "url": "https://other-url.com/webhook",
                    "content_type": "json",
                },
            },
        ]

        # Create async generator to mock paginated response
        async def mock_paginated_generator() -> (
            AsyncGenerator[List[Dict[str, Any]], None]
        ):
            yield webhooks

        with patch.object(
            client, "send_paginated_request", return_value=mock_paginated_generator()
        ):
            result = await client._get_existing_webhook(
                "https://example.com/integration/webhook"
            )

            assert result is None

    async def test_patch_webhook(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Test data
        webhook_id = "hook1"
        config_data = {
            "url": "https://example.com/integration/webhook",
            "content_type": "json",
            "secret": "test-secret",
        }

        with patch.object(client, "send_api_request", AsyncMock()) as mock_send:
            await client._patch_webhook(webhook_id, config_data)

            # Verify the API request was made correctly
            mock_send.assert_called_once_with(
                f"{client.github_host}/orgs/test-org/hooks/{webhook_id}",
                method="PATCH",
                json_data={"config": config_data},
            )

    async def test_upsert_webhook_create_new(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
            webhook_secret="test-secret",
        )

        # Mock that no existing webhook is found
        with (
            patch.object(client, "_get_existing_webhook", AsyncMock(return_value=None)),
            patch.object(client, "send_api_request", AsyncMock()) as mock_send,
        ):
            await client.upsert_webhook("https://example.com", ["push", "repository"])

            # Verify the webhook creation request was made correctly
            expected_data = {
                "name": "web",
                "active": True,
                "events": ["push", "repository"],
                "config": {
                    "url": "https://example.com/integration/webhook",
                    "content_type": "json",
                    "secret": "test-secret",
                },
            }

            mock_send.assert_called_once_with(
                f"{client.base_url}/orgs/test-org/hooks",
                method="POST",
                json_data=expected_data,
            )

    async def test_upsert_webhook_existing_needs_update(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
            webhook_secret="test-secret",
        )

        # Mock existing webhook without secret
        existing_webhook = {
            "id": "hook1",
            "config": {
                "url": "https://example.com/integration/webhook",
                "content_type": "json",
                # No secret
            },
        }

        with (
            patch.object(
                client,
                "_get_existing_webhook",
                AsyncMock(return_value=existing_webhook),
            ),
            patch.object(client, "_patch_webhook", AsyncMock()) as mock_patch,
        ):
            await client.upsert_webhook("https://example.com", ["push", "repository"])

            # Verify the patch request was made correctly
            expected_config = {
                "url": "https://example.com/integration/webhook",
                "content_type": "json",
                "secret": "test-secret",
            }

            mock_patch.assert_called_once_with("hook1", expected_config)

    async def test_upsert_webhook_existing_remove_secret(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
            webhook_secret=None,  # No webhook secret in the client
        )

        # Mock existing webhook with secret
        existing_webhook = {
            "id": "hook1",
            "config": {
                "url": "https://example.com/integration/webhook",
                "content_type": "json",
                "secret": "old-secret",  # Has a secret
            },
        }

        with (
            patch.object(
                client,
                "_get_existing_webhook",
                AsyncMock(return_value=existing_webhook),
            ),
            patch.object(client, "_patch_webhook", AsyncMock()) as mock_patch,
        ):
            await client.upsert_webhook("https://example.com", ["push", "repository"])

            # Verify the patch request was made correctly to remove secret
            expected_config = {
                "url": "https://example.com/integration/webhook",
                "content_type": "json",
                # No secret
            }

            mock_patch.assert_called_once_with("hook1", expected_config)

    async def test_upsert_webhook_no_changes_needed(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
            webhook_secret="test-secret",
        )

        # Mock existing webhook with matching configuration
        existing_webhook = {
            "id": "hook1",
            "config": {
                "url": "https://example.com/integration/webhook",
                "content_type": "json",
                "secret": "some-secret",  # Has some secret (specific value doesn't matter)
            },
        }

        with (
            patch.object(
                client,
                "_get_existing_webhook",
                AsyncMock(return_value=existing_webhook),
            ),
            patch.object(client, "_patch_webhook", AsyncMock()) as mock_patch,
            patch.object(client, "send_api_request", AsyncMock()) as mock_send,
        ):
            await client.upsert_webhook("https://example.com", ["push", "repository"])

            # Verify no API calls were made since no changes were needed
            mock_patch.assert_not_called()
            mock_send.assert_not_called()

    async def test_get_existing_webhook(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        """Test finding an existing webhook."""
        client = GithubWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        # Mock webhooks data
        hooks = [
            {
                "id": "hook1",
                "config": {
                    "url": "https://example.com/integration/webhook",
                    "content_type": "json",
                },
            },
            {
                "id": "hook2",
                "config": {
                    "url": "https://other-url.com/webhook",
                    "content_type": "json",
                },
            },
        ]

        # Create a mock response for the paginated request
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = hooks
        mock_response.headers = {}
        mock_response.status_code = 200

        with patch.object(
            client, "send_api_request", AsyncMock(return_value=mock_response)
        ):
            # Test finding an existing webhook
            webhook = await client._get_existing_webhook(
                "https://example.com/integration/webhook"
            )
            assert webhook is not None
            assert webhook["id"] == "hook1"

            # Test when webhook doesn't exist
            webhook = await client._get_existing_webhook(
                "https://non-existent.com/webhook"
            )
            assert webhook is None

    async def test_upsert_webhook_add_secret(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        """Test updating an existing webhook to add a secret."""
        client = GithubWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
            webhook_secret="test-secret",
        )

        # Mock an existing webhook without a secret
        existing_webhook = {
            "id": "hook1",
            "config": {
                "url": "https://example.com/integration/webhook",
                "content_type": "json",
            },
        }

        with (
            patch.object(
                client,
                "_get_existing_webhook",
                AsyncMock(return_value=existing_webhook),
            ),
            patch.object(client, "_patch_webhook", AsyncMock()) as mock_patch,
        ):
            await client.upsert_webhook("https://example.com", ["push", "repository"])

            # Verify the patch webhook call
            expected_config = {
                "url": "https://example.com/integration/webhook",
                "content_type": "json",
                "secret": "test-secret",
            }

            mock_patch.assert_called_once_with("hook1", expected_config)

    async def test_upsert_webhook_remove_secret(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        """Test updating an existing webhook to remove a secret."""
        client = GithubWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
            webhook_secret=None,  # No secret in client
        )

        # Mock an existing webhook with a secret
        existing_webhook = {
            "id": "hook1",
            "config": {
                "url": "https://example.com/integration/webhook",
                "content_type": "json",
                "secret": "old-secret",
            },
        }

        with (
            patch.object(
                client,
                "_get_existing_webhook",
                AsyncMock(return_value=existing_webhook),
            ),
            patch.object(client, "_patch_webhook", AsyncMock()) as mock_patch,
        ):
            await client.upsert_webhook("https://example.com", ["push", "repository"])

            # Verify the patch webhook call
            expected_config = {
                "url": "https://example.com/integration/webhook",
                "content_type": "json",
            }

            mock_patch.assert_called_once_with("hook1", expected_config)

    async def test_upsert_webhook_no_changes(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        """Test case where existing webhook doesn't need changes."""
        client = GithubWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
            webhook_secret="test-secret",
        )

        # Mock an existing webhook with a secret already
        existing_webhook = {
            "id": "hook1",
            "config": {
                "url": "https://example.com/integration/webhook",
                "content_type": "json",
                "secret": "some-secret",
            },
        }

        with (
            patch.object(
                client,
                "_get_existing_webhook",
                AsyncMock(return_value=existing_webhook),
            ),
            patch.object(client, "_patch_webhook", AsyncMock()) as mock_patch,
            patch.object(client, "send_api_request", AsyncMock()) as mock_send,
        ):
            await client.upsert_webhook("https://example.com", ["push", "repository"])

            # Verify no API calls were made
            mock_patch.assert_not_called()
            mock_send.assert_not_called()
