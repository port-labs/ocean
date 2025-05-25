import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any, cast

from github.webhook.webhook_factory.repository_webhook_factory import RepositoryWebhookFactory
from github.webhook.events import RepositoryEvents


@pytest.mark.asyncio
class TestRepositoryWebhookFactory:
    """Test the repository webhook factory"""

    @pytest.fixture
    def client(self) -> Any:
        """Initialize GitHub client mock"""
        client = MagicMock()
        client.rest = MagicMock()
        return client

    @pytest.fixture
    def repo_webhook_factory(self, client: Any) -> RepositoryWebhookFactory:
        """Create a RepositoryWebhookFactory instance"""
        return RepositoryWebhookFactory(client, "https://app.example.com")

    async def test_webhook_events(self, repo_webhook_factory: RepositoryWebhookFactory) -> None:
        """Test default webhook events configuration"""
        events = repo_webhook_factory.webhook_events()
        assert isinstance(events, RepositoryEvents)

    async def test_create_repository_webhook_success(
        self, repo_webhook_factory: RepositoryWebhookFactory, monkeypatch: Any
    ) -> None:
        """Test successful repository webhook creation"""
        # Mock create to return a successful response
        monkeypatch.setattr(
            repo_webhook_factory,
            "create",
            AsyncMock(
                return_value={
                    "id": 1,
                    "url": "https://app.example.com/integration/hook/owner/repo",
                }
            ),
        )
        result = await repo_webhook_factory.create_repository_webhook("owner", "repo")
        assert result is True
        cast(AsyncMock, repo_webhook_factory.create).assert_called_once_with(
            "https://app.example.com/integration/hook/owner/repo", "repos/owner/repo/hooks"
        )

    async def test_create_repository_webhook_failure(
        self, repo_webhook_factory: RepositoryWebhookFactory, monkeypatch: Any
    ) -> None:
        """Test failed repository webhook creation"""
        monkeypatch.setattr(
            repo_webhook_factory,
            "create",
            AsyncMock(side_effect=Exception("Failed to create webhook")),
        )
        result = await repo_webhook_factory.create_repository_webhook("owner", "repo")
        assert result is False

    async def test_create_webhooks_for_repositories(
        self, repo_webhook_factory: RepositoryWebhookFactory, monkeypatch: Any
    ) -> None:
        """Test creating webhooks for multiple repositories"""
        create_webhook_mock = AsyncMock(return_value=True)
        monkeypatch.setattr(repo_webhook_factory, "create_repository_webhook", create_webhook_mock)

        repositories = [
            {"full_name": "owner1/repo1"},
            {"full_name": "owner2/repo2"},
            {"full_name": "owner3/repo3"},
        ]

        await repo_webhook_factory.create_webhooks_for_repositories(repositories)

        assert create_webhook_mock.call_count == 3
        create_webhook_mock.assert_any_call("owner1", "repo1")
        create_webhook_mock.assert_any_call("owner2", "repo2")
        create_webhook_mock.assert_any_call("owner3", "repo3")
