from unittest.mock import AsyncMock

import pytest

from harbor.webhooks.events import HarborEventType
from harbor.webhooks.webhook_client import HarborWebhookClient


@pytest.fixture
def mock_client():
    return AsyncMock()


@pytest.fixture
def webhook_client(mock_client):
    return HarborWebhookClient(mock_client, webhook_secret="test-secret")


class TestHarborWebhookClient:
    def test_build_webhook_payload_with_secret(self, webhook_client):
        webhook_url = "https://example.com/webhook"
        event_types = [HarborEventType.PUSH_ARTIFACT, HarborEventType.DELETE_ARTIFACT]

        payload = webhook_client._build_webhook_payload(webhook_url, event_types)

        assert payload["name"] == "Port-Ocean-Harbor-Integration"
        assert payload["description"] == "Port Ocean Harbor Integration - Real-time updates"
        assert payload["enabled"] is True
        assert len(payload["event_types"]) == 2
        assert "PUSH_ARTIFACT" in payload["event_types"]
        assert "DELETE_ARTIFACT" in payload["event_types"]
        assert payload["targets"][0]["type"] == "http"
        assert payload["targets"][0]["address"] == webhook_url
        assert payload["targets"][0]["skip_cert_verify"] is True
        assert payload["targets"][0]["auth_header"] == "Authorization: Bearer test-secret"

    def test_build_webhook_payload_without_secret(self, mock_client):
        client = HarborWebhookClient(mock_client, webhook_secret=None)
        webhook_url = "https://example.com/webhook"
        event_types = [HarborEventType.PUSH_ARTIFACT]

        payload = client._build_webhook_payload(webhook_url, event_types)

        assert "auth_header" not in payload["targets"][0]

    @pytest.mark.asyncio
    async def test_get_webhook_policies(self, webhook_client, mock_client):
        expected_policies = [
            {"id": 1, "name": "test-webhook"},
            {"id": 2, "name": "Port-Ocean-Harbor-Integration"},
        ]
        mock_client.send_api_request.return_value = expected_policies

        policies = await webhook_client.get_webhook_policies("opensource")

        assert policies == expected_policies
        mock_client.send_api_request.assert_called_once_with("/projects/opensource/webhook/policies")

    @pytest.mark.asyncio
    async def test_get_existing_webhook_id_found(self, webhook_client, mock_client):
        mock_client.send_api_request.return_value = [
            {"id": 1, "name": "other-webhook"},
            {"id": 2, "name": "Port-Ocean-Harbor-Integration"},
            {"id": 3, "name": "another-webhook"},
        ]

        webhook_id = await webhook_client.get_existing_webhook_id("opensource")

        assert webhook_id == 2

    @pytest.mark.asyncio
    async def test_get_existing_webhook_id_not_found(self, webhook_client, mock_client):
        mock_client.send_api_request.return_value = [
            {"id": 1, "name": "other-webhook"},
            {"id": 3, "name": "another-webhook"},
        ]

        webhook_id = await webhook_client.get_existing_webhook_id("opensource")

        assert webhook_id is None

    @pytest.mark.asyncio
    async def test_get_existing_webhook_id_empty_list(self, webhook_client, mock_client):
        mock_client.send_api_request.return_value = []

        webhook_id = await webhook_client.get_existing_webhook_id("opensource")

        assert webhook_id is None

    @pytest.mark.asyncio
    async def test_get_existing_webhook_id_handles_exception(self, webhook_client, mock_client):
        mock_client.send_api_request.side_effect = Exception("API Error")

        webhook_id = await webhook_client.get_existing_webhook_id("opensource")

        assert webhook_id is None

    @pytest.mark.asyncio
    async def test_create_webhook(self, webhook_client, mock_client):
        expected_response = {"id": 1, "name": "Port-Ocean-Harbor-Integration"}
        mock_client.send_api_request.return_value = expected_response

        webhook_url = "https://example.com/webhook"
        event_types = [HarborEventType.PUSH_ARTIFACT, HarborEventType.DELETE_ARTIFACT]

        result = await webhook_client.create_webhook("opensource", webhook_url, event_types)

        assert result == expected_response
        mock_client.send_api_request.assert_called_once()
        call_args = mock_client.send_api_request.call_args
        assert call_args[0][0] == "/projects/opensource/webhook/policies"
        assert call_args[1]["method"] == "POST"
        assert "json_data" in call_args[1]
        assert call_args[1]["json_data"]["name"] == "Port-Ocean-Harbor-Integration"

    @pytest.mark.asyncio
    async def test_update_webhook(self, webhook_client, mock_client):
        expected_response = {"id": 5, "name": "Port-Ocean-Harbor-Integration"}
        mock_client.send_api_request.return_value = expected_response

        webhook_url = "https://example.com/webhook"
        event_types = [HarborEventType.PUSH_ARTIFACT]

        result = await webhook_client.update_webhook("production", 5, webhook_url, event_types)

        assert result == expected_response
        mock_client.send_api_request.assert_called_once()
        call_args = mock_client.send_api_request.call_args
        assert call_args[0][0] == "/projects/production/webhook/policies/5"
        assert call_args[1]["method"] == "PUT"
        assert "json_data" in call_args[1]

    @pytest.mark.asyncio
    async def test_upsert_webhook_creates_new_when_not_exists(self, webhook_client, mock_client):
        mock_client.send_api_request.side_effect = [
            [],
            {"id": 1, "name": "Port-Ocean-Harbor-Integration"},
        ]

        webhook_url = "https://example.com/webhook"
        event_types = [HarborEventType.PUSH_ARTIFACT]

        await webhook_client.upsert_webhook("opensource", webhook_url, event_types)

        assert mock_client.send_api_request.call_count == 2
        create_call = mock_client.send_api_request.call_args_list[1]
        assert create_call[1]["method"] == "POST"

    @pytest.mark.asyncio
    async def test_upsert_webhook_updates_when_exists(self, webhook_client, mock_client):
        mock_client.send_api_request.side_effect = [
            [{"id": 3, "name": "Port-Ocean-Harbor-Integration"}],
            {"id": 3, "name": "Port-Ocean-Harbor-Integration"},
        ]

        webhook_url = "https://example.com/webhook"
        event_types = [HarborEventType.PUSH_ARTIFACT]

        await webhook_client.upsert_webhook("production", webhook_url, event_types)

        assert mock_client.send_api_request.call_count == 2
        update_call = mock_client.send_api_request.call_args_list[1]
        assert update_call[1]["method"] == "PUT"
        assert "/webhook/policies/3" in update_call[0][0]

    @pytest.mark.asyncio
    async def test_upsert_webhook_handles_creation_error(self, webhook_client, mock_client):
        mock_client.send_api_request.side_effect = [
            [],
            Exception("API Error"),
        ]

        webhook_url = "https://example.com/webhook"
        event_types = [HarborEventType.PUSH_ARTIFACT]

        await webhook_client.upsert_webhook("opensource", webhook_url, event_types)

        assert mock_client.send_api_request.call_count == 2

    @pytest.mark.asyncio
    async def test_upsert_webhook_handles_update_error(self, webhook_client, mock_client):
        mock_client.send_api_request.side_effect = [
            [{"id": 2, "name": "Port-Ocean-Harbor-Integration"}],
            Exception("API Error"),
        ]

        webhook_url = "https://example.com/webhook"
        event_types = [HarborEventType.PUSH_ARTIFACT]

        await webhook_client.upsert_webhook("production", webhook_url, event_types)

        assert mock_client.send_api_request.call_count == 2
