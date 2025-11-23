import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any, cast

from github.webhook.webhook_factory.organization_webhook_factory import OrganizationWebhookFactory
from github.webhook.events import OrganizationEvents


class AsyncIterator:
    """Helper class to properly mock async iterators in tests"""

    def __init__(self, items: list[Any]) -> None:
        self.items = items
        self.index = 0

    def __aiter__(self) -> "AsyncIterator":
        return self

    async def __anext__(self) -> Any:
        if self.index >= len(self.items):
            raise StopAsyncIteration
        value = self.items[self.index]
        self.index += 1
        return value


@pytest.mark.asyncio
class TestOrganizationWebhookFactory:
    """Test the organization webhook factory"""

    @pytest.fixture
    def client(self) -> Any:
        """Initialize GitHub client mock"""
        client = MagicMock()
        client.rest = MagicMock()
        return client

    @pytest.fixture
    def org_webhook_factory(self, client: Any) -> OrganizationWebhookFactory:
        """Create an OrganizationWebhookFactory instance"""
        return OrganizationWebhookFactory(client, "https://app.example.com")

    async def test_webhook_events(self, org_webhook_factory: OrganizationWebhookFactory) -> None:
        """Test default webhook events configuration"""
        events = org_webhook_factory.webhook_events()
        assert isinstance(events, OrganizationEvents)

    async def test_create_organization_webhook_success(
        self, org_webhook_factory: OrganizationWebhookFactory, monkeypatch: Any
    ) -> None:
        """Test successful organization webhook creation"""
        # Mock create to return a successful response
        monkeypatch.setattr(
            org_webhook_factory,
            "create",
            AsyncMock(
                return_value={
                    "id": 1,
                    "url": "https://app.example.com/integration/hook/org/test-org",
                }
            ),
        )
        result = await org_webhook_factory.create_organization_webhook("test-org")
        assert result is True
        cast(AsyncMock, org_webhook_factory.create).assert_called_once_with(
            "https://app.example.com/integration/hook/org/test-org", "orgs/test-org/hooks"
        )

    async def test_create_organization_webhook_failure(
        self, org_webhook_factory: OrganizationWebhookFactory, monkeypatch: Any
    ) -> None:
        """Test failed organization webhook creation"""
        monkeypatch.setattr(
            org_webhook_factory,
            "create",
            AsyncMock(side_effect=Exception("Failed to create webhook")),
        )
        result = await org_webhook_factory.create_organization_webhook("test-org")
        assert result is False

    async def test_create_webhooks_for_organizations(
        self, org_webhook_factory: OrganizationWebhookFactory, monkeypatch: Any
    ) -> None:
        """Test creating webhooks for all organizations"""
        create_webhook_mock = AsyncMock(return_value=True)
        monkeypatch.setattr(org_webhook_factory, "create_organization_webhook", create_webhook_mock)

        mock_batches: list[list[dict[str, Any]]] = [
            [{"login": "org1"}, {"login": "org2"}],
            [{"login": "org3"}],
        ]
        monkeypatch.setattr(
            org_webhook_factory._client.rest,
            "get_paginated_resource",
            lambda endpoint: AsyncIterator(mock_batches),
        )

        await org_webhook_factory.create_webhooks_for_organizations()

        assert create_webhook_mock.call_count == 3
        create_webhook_mock.assert_any_call("org1")
        create_webhook_mock.assert_any_call("org2")
        create_webhook_mock.assert_any_call("org3")
