import pytest
from unittest.mock import AsyncMock, patch
from typing import Any, AsyncGenerator, Dict, List
from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.webhook.clients.base_webhook_client import HookTarget
from github.webhook.clients.webhook_client import GithubWebhookClient
from github.webhook.events import WEBHOOK_CREATE_EVENTS


@pytest.mark.asyncio
class TestGithubWebhookClient:
    async def test_get_supported_events(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        assert client.get_supported_events() == WEBHOOK_CREATE_EVENTS

    async def test_get_existing_webhook_found(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )
        target = HookTarget(
            target_type="organization",
            hooks_url=f"{client.base_url}/orgs/test-org/hooks",
            single_hook_url_template=(
                f"{client.base_url}/orgs/test-org/hooks/{{webhook_id}}"
            ),
            log_scope={"organization": "test-org"},
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
                "https://example.com/integration/webhook",
                target,
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
        target = HookTarget(
            target_type="organization",
            hooks_url=f"{client.base_url}/orgs/test-org/hooks",
            single_hook_url_template=(
                f"{client.base_url}/orgs/test-org/hooks/{{webhook_id}}"
            ),
            log_scope={"organization": "test-org"},
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
                "https://example.com/integration/webhook",
                target,
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
        target = HookTarget(
            target_type="organization",
            hooks_url=f"{client.base_url}/orgs/test-org/hooks",
            single_hook_url_template=(
                f"{client.base_url}/orgs/test-org/hooks/{{webhook_id}}"
            ),
            log_scope={"organization": "test-org"},
        )

        with patch.object(client, "send_api_request", AsyncMock()) as mock_send:
            await client._patch_webhook(webhook_id, config_data, target)

            # Verify the API request was made correctly
            mock_send.assert_called_once_with(
                f"{client.base_url}/orgs/test-org/hooks/{webhook_id}",
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
            await client.upsert_webhook("https://example.com")

            # Verify the webhook creation request was made correctly
            expected_data = {
                "name": "web",
                "active": True,
                "events": WEBHOOK_CREATE_EVENTS,
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
        expected_target = HookTarget(
            target_type="organization",
            hooks_url=f"{client.base_url}/orgs/test-org/hooks",
            single_hook_url_template=(
                f"{client.base_url}/orgs/test-org/hooks/{{webhook_id}}"
            ),
            log_scope={"organization": "test-org"},
        )

        with (
            patch.object(
                client,
                "_get_existing_webhook",
                AsyncMock(return_value=existing_webhook),
            ),
            patch.object(client, "_patch_webhook", AsyncMock()) as mock_patch,
        ):
            await client.upsert_webhook("https://example.com")

            # Verify the patch request was made correctly
            expected_config = {
                "url": "https://example.com/integration/webhook",
                "content_type": "json",
                "secret": "test-secret",
            }

            mock_patch.assert_called_once_with(
                "hook1", expected_config, expected_target
            )

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
        expected_target = HookTarget(
            target_type="organization",
            hooks_url=f"{client.base_url}/orgs/test-org/hooks",
            single_hook_url_template=(
                f"{client.base_url}/orgs/test-org/hooks/{{webhook_id}}"
            ),
            log_scope={"organization": "test-org"},
        )

        with (
            patch.object(
                client,
                "_get_existing_webhook",
                AsyncMock(return_value=existing_webhook),
            ),
            patch.object(client, "_patch_webhook", AsyncMock()) as mock_patch,
        ):
            await client.upsert_webhook("https://example.com")

            # Verify the patch request was made correctly to remove secret
            expected_config = {
                "url": "https://example.com/integration/webhook",
                "content_type": "json",
                # No secret
            }

            mock_patch.assert_called_once_with(
                "hook1", expected_config, expected_target
            )

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
            await client.upsert_webhook("https://example.com")

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
        target = HookTarget(
            target_type="organization",
            hooks_url=f"{client.base_url}/orgs/test-org/hooks",
            single_hook_url_template=(
                f"{client.base_url}/orgs/test-org/hooks/{{webhook_id}}"
            ),
            log_scope={"organization": "test-org"},
        )

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

        async def mock_paginated_generator() -> (
            AsyncGenerator[List[Dict[str, Any]], None]
        ):
            yield hooks

        with patch.object(
            client, "send_paginated_request", return_value=mock_paginated_generator()
        ):
            webhook = await client._get_existing_webhook(
                "https://example.com/integration/webhook",
                target,
            )
            assert webhook is not None
            assert webhook["id"] == "hook1"

            webhook = await client._get_existing_webhook(
                "https://non-existent.com/webhook",
                target,
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
        expected_target = HookTarget(
            target_type="organization",
            hooks_url=f"{client.base_url}/orgs/test-org/hooks",
            single_hook_url_template=(
                f"{client.base_url}/orgs/test-org/hooks/{{webhook_id}}"
            ),
            log_scope={"organization": "test-org"},
        )

        with (
            patch.object(
                client,
                "_get_existing_webhook",
                AsyncMock(return_value=existing_webhook),
            ),
            patch.object(client, "_patch_webhook", AsyncMock()) as mock_patch,
        ):
            await client.upsert_webhook("https://example.com")

            # Verify the patch webhook call
            expected_config = {
                "url": "https://example.com/integration/webhook",
                "content_type": "json",
                "secret": "test-secret",
            }

            mock_patch.assert_called_once_with(
                "hook1", expected_config, expected_target
            )

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
        expected_target = HookTarget(
            target_type="organization",
            hooks_url=f"{client.base_url}/orgs/test-org/hooks",
            single_hook_url_template=(
                f"{client.base_url}/orgs/test-org/hooks/{{webhook_id}}"
            ),
            log_scope={"organization": "test-org"},
        )

        with (
            patch.object(
                client,
                "_get_existing_webhook",
                AsyncMock(return_value=existing_webhook),
            ),
            patch.object(client, "_patch_webhook", AsyncMock()) as mock_patch,
        ):
            await client.upsert_webhook("https://example.com")

            # Verify the patch webhook call
            expected_config = {
                "url": "https://example.com/integration/webhook",
                "content_type": "json",
            }

            mock_patch.assert_called_once_with(
                "hook1", expected_config, expected_target
            )

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
            await client.upsert_webhook("https://example.com")

            # Verify no API calls were made
            mock_patch.assert_not_called()
            mock_send.assert_not_called()
