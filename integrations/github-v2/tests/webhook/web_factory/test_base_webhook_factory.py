import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any

from github.webhook.webhook_factory._base_webhook_factory import BaseWebhookFactory
from github.webhook.events import EventConfig


@pytest.mark.asyncio
class TestBaseWebhookFactory:
    """Test the abstract base webhook factory"""

    @pytest.fixture
    def mock_events(self) -> MagicMock:
        """Create a mock events object"""
        events = MagicMock()
        events.to_dict.return_value = {
            "push": True,
            "pull_request": True,
            "issues": False,
        }
        return events

    @pytest.fixture
    def concrete_factory(
        self, mock_events: MagicMock
    ) -> BaseWebhookFactory[EventConfig]:
        """Create a concrete implementation of the BaseWebhookFactory"""

        class ConcreteFactory(BaseWebhookFactory[EventConfig]):
            def webhook_events(self) -> MagicMock:
                return mock_events

        client = MagicMock()
        client.rest = MagicMock()
        return ConcreteFactory(client, "https://app.example.com")

    async def test_webhook_exists(
        self,
        concrete_factory: BaseWebhookFactory[EventConfig],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test checking if a webhook already exists"""
        # Mock the async generator
        async def mock_generator():
            yield [
                {"id": 1, "config": {"url": "https://app.example.com/hook/123"}},
                {"id": 2, "config": {"url": "https://app.example.com/hook/456"}},
            ]

        monkeypatch.setattr(
            concrete_factory._client.rest,
            "get_paginated_resource",
            lambda endpoint: mock_generator(),
        )

        # Test with matching URL
        exists = await concrete_factory._exists(
            "https://app.example.com/hook/123", "repos/owner/repo/hooks"
        )
        assert exists is True

        # Test with non-matching URL
        exists = await concrete_factory._exists(
            "https://app.example.com/hook/789", "repos/owner/repo/hooks"
        )
        assert exists is False

    async def test_build_payload(
        self,
        concrete_factory: BaseWebhookFactory[EventConfig],
        mock_events: MagicMock,
    ) -> None:
        """Test building webhook payload"""
        payload = concrete_factory._build_payload(
            "https://app.example.com/hook/123", mock_events
        )

        assert payload["name"] == "web"
        assert payload["active"] is True
        assert payload["config"]["url"] == "https://app.example.com/hook/123"
        assert payload["config"]["content_type"] == "json"
        assert payload["config"]["insecure_ssl"] == "0"
        assert "push" in payload["events"]
        assert "pull_request" in payload["events"]
        assert "issues" not in payload["events"]  # False in mock

    async def test_validate_response(
        self, concrete_factory: BaseWebhookFactory[EventConfig]
    ) -> None:
        """Test webhook response validation"""
        valid_response = {
            "id": 1,
            "config": {"url": "https://app.example.com/hook/123"},
            "url": "https://api.github.com/repos/owner/repo/hooks/1",
        }
        invalid_response1 = {"config": {"url": "https://app.example.com/hook/123"}}
        invalid_response2 = {"id": 1}
        empty_response: dict[str, Any] = {}

        assert concrete_factory._validate_response(valid_response) is True
        assert concrete_factory._validate_response(invalid_response1) is False
        assert concrete_factory._validate_response(invalid_response2) is False
        assert concrete_factory._validate_response(empty_response) is False

    async def test_create_webhook_success(
        self,
        concrete_factory: BaseWebhookFactory[EventConfig],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test successful webhook creation"""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "id": 1,
            "config": {"url": "https://app.example.com/hook/123"},
            "url": "https://api.github.com/repos/owner/repo/hooks/1",
        }
        monkeypatch.setattr(concrete_factory, "_exists", AsyncMock(return_value=False))
        monkeypatch.setattr(
            concrete_factory,
            "_send_request",
            AsyncMock(
                return_value=mock_response
            ),
        )

        response = await concrete_factory.create(
            "https://app.example.com/hook/123", "repos/owner/repo/hooks"
        )
        assert response["id"] == 1
        assert response["config"]["url"] == "https://app.example.com/hook/123"

    async def test_create_webhook_already_exists(
        self,
        concrete_factory: BaseWebhookFactory[EventConfig],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test webhook creation when webhook already exists"""
        monkeypatch.setattr(concrete_factory, "_exists", AsyncMock(return_value=True))

        response = await concrete_factory.create(
            "https://app.example.com/hook/123", "repos/owner/repo/hooks"
        )
        assert response == {}
