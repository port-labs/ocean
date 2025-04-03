import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any

from gitlab.webhook.webhook_factory._base_webhook_factory import BaseWebhookFactory
from gitlab.webhook.events import EventConfig


@pytest.mark.asyncio
class TestBaseWebhookFactory:
    """Test the abstract base webhook factory"""

    @pytest.fixture
    def mock_events(self) -> MagicMock:
        """Create a mock events object"""
        events = MagicMock()
        events.to_dict.return_value = {
            "push_events": True,
            "merge_requests_events": True,
            "issues_events": True,
        }
        return events

    @pytest.fixture
    def concrete_factory(
        self, mock_events: MagicMock
    ) -> BaseWebhookFactory[EventConfig]:
        """Create a concrete implementation of the abstract BaseWebhookFactory"""

        class ConcreteFactory(BaseWebhookFactory[EventConfig]):
            def webhook_events(self) -> MagicMock:
                return mock_events

        client = MagicMock()
        client.rest = MagicMock()
        # Patch the method with a proper async iterator
        client.rest.get_paginated_resource = MagicMock()
        return ConcreteFactory(client, "https://app.example.com")

    async def test_webhook_exists(
        self,
        concrete_factory: BaseWebhookFactory[EventConfig],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test checking if a webhook already exists"""

        exists_mock = AsyncMock(side_effect=[True, False])
        monkeypatch.setattr(concrete_factory, "_exists", exists_mock)

        # Test with matching URL
        exists = await concrete_factory._exists(
            "https://app.example.com/hook/123", "groups/123/hooks"
        )
        assert exists is True

        # Test with non-matching URL
        exists = await concrete_factory._exists(
            "https://app.example.com/hook/456", "groups/123/hooks"
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
        assert payload["url"] == "https://app.example.com/hook/123"
        assert payload["push_events"] is True
        assert payload["merge_requests_events"] is True
        assert payload["issues_events"] is True

    async def test_validate_response(
        self, concrete_factory: BaseWebhookFactory[EventConfig]
    ) -> None:
        """Test webhook response validation"""
        valid_response = {"id": 1, "url": "https://app.example.com/hook/123"}
        invalid_response1 = {"url": "https://app.example.com/hook/123"}
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
        monkeypatch.setattr(concrete_factory, "_exists", AsyncMock(return_value=False))
        monkeypatch.setattr(
            concrete_factory,
            "_send_request",
            AsyncMock(
                return_value={"id": 1, "url": "https://app.example.com/hook/123"}
            ),
        )

        response = await concrete_factory.create(
            "https://app.example.com/hook/123", "groups/123/hooks"
        )
        assert response["id"] == 1
        assert response["url"] == "https://app.example.com/hook/123"

    async def test_create_webhook_already_exists(
        self,
        concrete_factory: BaseWebhookFactory[EventConfig],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test webhook creation when webhook already exists"""
        monkeypatch.setattr(concrete_factory, "_exists", AsyncMock(return_value=True))

        response = await concrete_factory.create(
            "https://app.example.com/hook/123", "groups/123/hooks"
        )
        assert response == {}

    async def test_create_webhook_failure(
        self,
        concrete_factory: BaseWebhookFactory[EventConfig],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test webhook creation failure"""
        monkeypatch.setattr(concrete_factory, "_exists", AsyncMock(return_value=False))
        monkeypatch.setattr(
            concrete_factory,
            "_send_request",
            AsyncMock(side_effect=Exception("API Error")),
        )

        with pytest.raises(Exception):
            await concrete_factory.create(
                "https://app.example.com/hook/123", "groups/123/hooks"
            )
