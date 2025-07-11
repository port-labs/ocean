import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any, cast
from unittest.mock import call

from gitlab.webhook.webhook_factory.group_webhook_factory import GroupWebHook
from gitlab.webhook.events import GroupEvents


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
class TestGroupWebHook:
    """Test the group webhook implementation"""

    @pytest.fixture
    def client(self) -> Any:
        """Initialize GitLab client with test configuration"""
        client = MagicMock()
        client.rest = MagicMock()
        return client

    @pytest.fixture
    def group_webhook(self, client: Any) -> GroupWebHook:
        """Create a GroupWebHook instance"""

        return GroupWebHook(client, "https://app.example.com")

    async def test_webhook_events(self, group_webhook: GroupWebHook) -> None:
        """Test default webhook events configuration"""
        events = group_webhook.webhook_events()
        assert isinstance(events, GroupEvents)

    async def test_create_group_webhook_success(
        self, group_webhook: GroupWebHook, monkeypatch: Any
    ) -> None:
        """Test successful group webhook creation"""
        # Mock create to return a successful response
        monkeypatch.setattr(
            group_webhook,
            "create",
            AsyncMock(
                return_value={
                    "id": 1,
                    "url": "https://app.example.com/integration/hook/123",
                }
            ),
        )
        result = await group_webhook.create_group_webhook("123")
        assert result is True
        cast(AsyncMock, group_webhook.create).assert_called_once_with(
            "https://app.example.com/integration/hook/123", "groups/123/hooks"
        )

    async def test_create_group_webhook_failure(
        self, group_webhook: GroupWebHook, monkeypatch: Any
    ) -> None:
        """Test failed group webhook creation"""
        monkeypatch.setattr(
            group_webhook,
            "create",
            AsyncMock(side_effect=Exception("Failed to create webhook")),
        )
        result = await group_webhook.create_group_webhook("123")
        assert result is False

    async def test_create_webhooks_for_all_groups(
        self, group_webhook: GroupWebHook, monkeypatch: Any
    ) -> None:
        """Test creating webhooks for all groups"""
        # Mock the create method to return a successful response
        create_mock = AsyncMock(
            return_value={
                "id": 1,
                "url": "https://app.example.com/integration/hook/123",
            }
        )
        monkeypatch.setattr(group_webhook, "create", create_mock)

        mock_groups = [
            {"id": "123", "name": "Group1"},
            {"id": "456", "name": "Group2"},
            {"id": "789", "name": "Group3"},
        ]
        monkeypatch.setattr(
            group_webhook._client,
            "get_parent_groups",
            lambda owned: AsyncIterator([mock_groups]),
        )

        await group_webhook.create_webhooks_for_all_groups()

        assert create_mock.call_count == 3
        create_mock.assert_has_calls(
            [
                call(
                    "https://app.example.com/integration/hook/123", "groups/123/hooks"
                ),
                call(
                    "https://app.example.com/integration/hook/456", "groups/456/hooks"
                ),
                call(
                    "https://app.example.com/integration/hook/789", "groups/789/hooks"
                ),
            ]
        )
