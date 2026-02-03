import pytest
from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import AsyncMock, patch

from github.clients.auth.abstract_authenticator import AbstractGitHubAuthenticator
from github.clients.auth.github_app_authenticator import GitHubAppAuthenticator
from github.webhook.clients.base_webhook_client import HookTarget
from github.webhook.clients.personal_account_webhook_client import (
    GithubPersonalAccountWebhookClient,
)
from github.webhook.events import WEBHOOK_CREATE_EVENTS


@pytest.mark.asyncio
class TestGithubPersonalAccountWebhookClient:
    async def test_get_supported_events(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubPersonalAccountWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )

        disallowed_for_repo = {"organization", "team", "membership", "member"}
        expected = [e for e in WEBHOOK_CREATE_EVENTS if e not in disallowed_for_repo]
        assert client.get_supported_events() == expected

    async def test_get_existing_webhook_found(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubPersonalAccountWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )
        target = HookTarget(
            target_type="repository",
            hooks_url=f"{client.base_url}/repos/test-user/test-repo/hooks",
            single_hook_url_template=(
                f"{client.base_url}/repos/test-user/test-repo/hooks/{{webhook_id}}"
            ),
            log_scope={"organization": "test-org", "repository": "test-repo"},
        )

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
        client = GithubPersonalAccountWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
        )
        target = HookTarget(
            target_type="repository",
            hooks_url=f"{client.base_url}/repos/test-user/test-repo/hooks",
            single_hook_url_template=(
                f"{client.base_url}/repos/test-user/test-repo/hooks/{{webhook_id}}"
            ),
            log_scope={"organization": "test-org", "repository": "test-repo"},
        )

        webhooks = [
            {
                "id": "hook1",
                "config": {
                    "url": "https://different-url.com/webhook",
                    "content_type": "json",
                },
            },
        ]

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

    async def test_upsert_webhook_create_new(
        self, authenticator: AbstractGitHubAuthenticator
    ) -> None:
        client = GithubPersonalAccountWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=authenticator,
            webhook_secret="test-secret",
        )

        target = HookTarget(
            target_type="repository",
            hooks_url=f"{client.base_url}/repos/test-user/test-repo/hooks",
            single_hook_url_template=(
                f"{client.base_url}/repos/test-user/test-repo/hooks/{{webhook_id}}"
            ),
            log_scope={"organization": "test-org", "repository": "test-repo"},
        )

        async def mock_iter_hook_targets() -> AsyncGenerator[HookTarget, None]:
            yield target

        with (
            patch.object(client, "iter_hook_targets", new=mock_iter_hook_targets),
            patch.object(client, "_get_existing_webhook", AsyncMock(return_value=None)),
            patch.object(client, "send_api_request", AsyncMock()) as mock_send,
        ):
            await client.upsert_webhook("https://example.com")

        disallowed_for_repo = {"organization", "team", "membership", "member"}
        expected_events = [
            e for e in WEBHOOK_CREATE_EVENTS if e not in disallowed_for_repo
        ]
        expected_data = {
            "name": "web",
            "active": True,
            "events": expected_events,
            "config": {
                "url": "https://example.com/integration/webhook",
                "content_type": "json",
                "secret": "test-secret",
            },
        }

        mock_send.assert_called_once_with(
            target.hooks_url,
            method="POST",
            json_data=expected_data,
        )

    async def test_iter_owned_repositories_uses_installation_endpoint_when_app_auth(
        self,
    ) -> None:
        client = GithubPersonalAccountWebhookClient(
            token="test-token",
            organization="test-org",
            github_host="https://api.github.com",
            authenticator=GitHubAppAuthenticator(
                app_id="app",
                private_key="key",
                organization="test-org",
                github_host="https://api.github.com",
                installation_id="123",
            ),
        )

        async def mock_paginated_request(
            url: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[Dict[str, Any], None]:
            yield {"total_count": 1, "repositories": [{"id": 1, "name": "repo1"}]}

        with patch.object(
            client, "send_paginated_request", side_effect=mock_paginated_request
        ) as mock_request:
            repos = [batch async for batch in client._iter_owned_repositories()]

        assert repos == [[{"id": 1, "name": "repo1"}]]
        mock_request.assert_called_once_with(
            "https://api.github.com/installation/repositories"
        )
