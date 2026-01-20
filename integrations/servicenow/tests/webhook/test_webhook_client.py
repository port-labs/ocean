import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from webhook.webhook_client import ServicenowWebhookClient
from webhook.processors.utils.outbound_message import (
    REST_MESSAGE_NAME,
    find_rest_message,
    create_rest_message_parent,
    create_rest_message_if_not_exists,
)
from webhook.processors.utils.business_rule import (
    generate_business_rule_script,
    build_upsert_rule_payload,
    build_delete_rule_payload,
    submit_business_rules,
    business_rule_exists,
    create_business_rule_if_not_exists,
)
from tests.conftest import SAMPLE_INCIDENT_DATA
from typing import Dict, Any


class TestServicenowWebhookClient:
    """Test suite for ServiceNow webhook client."""

    @pytest.mark.asyncio
    async def test_make_request_success(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test successful API request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"sys_id": "test123"}}
        mock_response.raise_for_status.return_value = None

        with patch.object(
            webhook_client.http_client, "request", return_value=mock_response
        ):
            with patch.object(
                webhook_client.authenticator,
                "get_headers",
                return_value={"Authorization": "Basic test"},
            ):
                result = await webhook_client._make_request(
                    "https://test-url.com/api/test"
                )

                assert result == {"result": {"sys_id": "test123"}}

    @pytest.mark.asyncio
    async def test_make_request_http_status_error(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test handling HTTP status error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        with patch.object(
            webhook_client.http_client, "request", return_value=mock_response
        ):
            with patch.object(
                webhook_client.authenticator,
                "get_headers",
                return_value={"Authorization": "Basic test"},
            ):
                result = await webhook_client._make_request(
                    "https://test-url.com/api/test"
                )

                assert result is None

    @pytest.mark.asyncio
    async def test_make_request_http_error(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test handling general HTTP error."""
        with patch.object(
            webhook_client.http_client,
            "request",
            side_effect=httpx.HTTPError("Connection failed"),
        ):
            with patch.object(
                webhook_client.authenticator,
                "get_headers",
                return_value={"Authorization": "Basic test"},
            ):
                result = await webhook_client._make_request(
                    "https://test-url.com/api/test"
                )

                assert result is None

    @pytest.mark.asyncio
    async def test_create_webhook_success(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test successful webhook creation for valid tables."""
        with patch(
            "webhook.webhook_client.create_rest_message_if_not_exists",
            AsyncMock(return_value=REST_MESSAGE_NAME),
        ):
            with patch(
                "webhook.webhook_client.create_business_rule_if_not_exists",
                AsyncMock(),
            ) as mock_create_rule:
                await webhook_client.create_webhook(
                    "https://example.com", ["incident", "sys_user_group"]
                )

                assert mock_create_rule.call_count == 2

    @pytest.mark.asyncio
    async def test_create_webhook_skips_unknown_tables(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test that unknown tables are skipped."""
        with patch(
            "webhook.webhook_client.create_rest_message_if_not_exists",
            AsyncMock(return_value=REST_MESSAGE_NAME),
        ):
            with patch(
                "webhook.webhook_client.create_business_rule_if_not_exists",
                AsyncMock(),
            ) as mock_create_rule:
                await webhook_client.create_webhook(
                    "https://example.com", ["incident", "unknown_table"]
                )

                assert mock_create_rule.call_count == 1

    @pytest.mark.asyncio
    async def test_create_webhook_no_rest_message(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test handling when REST message creation fails."""
        with patch(
            "webhook.webhook_client.create_rest_message_if_not_exists",
            AsyncMock(return_value=None),
        ):
            with patch(
                "webhook.webhook_client.create_business_rule_if_not_exists",
                AsyncMock(),
            ) as mock_create_rule:
                await webhook_client.create_webhook("https://example.com", ["incident"])

                mock_create_rule.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_record_by_sys_id_found(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test retrieving a record by sys_id when it exists."""
        mock_response = {"result": SAMPLE_INCIDENT_DATA}

        with patch.object(
            webhook_client, "_make_request", AsyncMock(return_value=mock_response)
        ):
            result = await webhook_client.get_record_by_sys_id(
                "incident", SAMPLE_INCIDENT_DATA["sys_id"]
            )

            assert result == SAMPLE_INCIDENT_DATA

    @pytest.mark.asyncio
    async def test_get_record_by_sys_id_not_found(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test retrieving a record that doesn't exist."""
        with patch.object(
            webhook_client, "_make_request", AsyncMock(return_value=None)
        ):
            result = await webhook_client.get_record_by_sys_id(
                "incident", "nonexistent_id"
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_get_record_by_sys_id_empty_result(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test retrieving a record with empty result."""
        mock_response: Dict[str, Any] = {"result": {}}

        with patch.object(
            webhook_client, "_make_request", AsyncMock(return_value=mock_response)
        ):
            result = await webhook_client.get_record_by_sys_id("incident", "empty_id")

            assert result is None


class TestOutboundMessage:
    """Test suite for outbound message utility functions."""

    @pytest.mark.asyncio
    async def test_find_rest_message_found(self) -> None:
        """Test finding an existing REST message."""
        mock_request = AsyncMock(return_value={"result": [{"sys_id": "rest_msg_123"}]})

        result = await find_rest_message(
            mock_request,
            "https://test.service-now.com/api/now/table",
            "Ocean Port Outbound",
        )

        assert result == "rest_msg_123"

    @pytest.mark.asyncio
    async def test_find_rest_message_not_found(self) -> None:
        """Test when REST message does not exist."""
        mock_request = AsyncMock(return_value={"result": []})

        result = await find_rest_message(
            mock_request,
            "https://test.service-now.com/api/now/table",
            "Nonexistent Message",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_create_rest_message_parent_success(self) -> None:
        """Test creating a REST message parent successfully."""
        mock_request = AsyncMock(return_value={"result": {"sys_id": "new_parent_id"}})

        result = await create_rest_message_parent(
            mock_request,
            "https://test.service-now.com/api/now/table",
            "https://example.com/webhook",
        )

        assert result == "new_parent_id"

    @pytest.mark.asyncio
    async def test_create_rest_message_parent_failure(self) -> None:
        """Test handling REST message parent creation failure."""
        mock_request = AsyncMock(return_value=None)

        result = await create_rest_message_parent(
            mock_request,
            "https://test.service-now.com/api/now/table",
            "https://example.com/webhook",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_create_rest_message_if_not_exists_existing(self) -> None:
        """Test using an existing REST message."""
        mock_request = AsyncMock(return_value={"result": [{"sys_id": "existing_id"}]})

        result = await create_rest_message_if_not_exists(
            mock_request,
            "https://test.service-now.com/api/now/table",
            "https://example.com/webhook",
        )

        assert result == REST_MESSAGE_NAME

    @pytest.mark.asyncio
    async def test_create_rest_message_if_not_exists_create_new(self) -> None:
        """Test creating a new REST message."""
        mock_request = AsyncMock(
            side_effect=[
                {"result": []},
                {"result": {"sys_id": "new_parent_id"}},
                {"result": {"sys_id": "new_fn_id"}},
            ]
        )

        result = await create_rest_message_if_not_exists(
            mock_request,
            "https://test.service-now.com/api/now/table",
            "https://example.com/webhook",
        )

        assert result == REST_MESSAGE_NAME

    @pytest.mark.asyncio
    async def test_create_rest_message_if_not_exists_creation_failure(self) -> None:
        """Test handling REST message creation failure."""
        mock_request = AsyncMock(
            side_effect=[
                {"result": []},
                None,
            ]
        )

        result = await create_rest_message_if_not_exists(
            mock_request,
            "https://test.service-now.com/api/now/table",
            "https://example.com/webhook",
        )

        assert result is None


class TestBusinessRule:
    """Test suite for business rule utility functions."""

    def test_generate_business_rule_script_basic(self) -> None:
        """Test generating a business rule script with basic fields."""
        fields = ["sys_id", "number", "state"]
        script = generate_business_rule_script(REST_MESSAGE_NAME, fields)

        assert "RESTMessageV2" in script
        assert REST_MESSAGE_NAME in script
        assert '"sys_id": current.sys_id + "",' in script
        assert '"number": current.number + "",' in script
        assert '"state": current.state + ""' in script

    def test_generate_business_rule_script_with_dot_fields(self) -> None:
        """Test generating a business rule script with fields containing dots."""
        fields = ["caller_id.name", "assignment_group.name"]
        script = generate_business_rule_script(REST_MESSAGE_NAME, fields)

        assert '"caller_id_name": current.caller_id.name + "",' in script
        assert '"assignment_group_name": current.assignment_group.name + ""' in script

    def test_generate_business_rule_script_delete_event(self) -> None:
        """Test generating a business rule script for delete events."""
        fields = ["sys_id", "number"]
        script = generate_business_rule_script(
            REST_MESSAGE_NAME, fields, delete_event=True
        )

        assert "previous.sys_id" in script
        assert "previous.number" in script
        assert "current." not in script

    def test_build_upsert_rule_payload(self) -> None:
        """Test building upsert rule payload."""
        payload = build_upsert_rule_payload(
            "Ocean Port: incident",
            "incident",
            ["sys_id", "number"],
            200,
            REST_MESSAGE_NAME,
        )

        assert payload["name"] == "Ocean Port: incident"
        assert payload["collection"] == "incident"
        assert payload["action_insert"] == "true"
        assert payload["action_update"] == "true"
        assert payload["action_delete"] == "false"
        assert payload["order"] == 200

    def test_build_delete_rule_payload(self) -> None:
        """Test building delete rule payload."""
        payload = build_delete_rule_payload(
            "Ocean Port: incident",
            "incident",
            ["sys_id", "number"],
            200,
            REST_MESSAGE_NAME,
        )

        assert payload["name"] == "Ocean Port: incident (delete)"
        assert payload["collection"] == "incident"
        assert payload["action_insert"] == "false"
        assert payload["action_update"] == "false"
        assert payload["action_delete"] == "true"
        assert payload["when"] == "after"

    @pytest.mark.asyncio
    async def test_business_rule_exists_true(self) -> None:
        """Test checking if a business rule exists."""
        mock_request = AsyncMock(return_value={"result": [{"sys_id": "rule_123"}]})

        result = await business_rule_exists(
            mock_request,
            "https://test.service-now.com/api/now/table",
            "incident to port",
            "incident",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_business_rule_exists_false(self) -> None:
        """Test checking when business rule does not exist."""
        mock_request = AsyncMock(return_value={"result": []})

        result = await business_rule_exists(
            mock_request,
            "https://test.service-now.com/api/now/table",
            "nonexistent rule",
            "incident",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_submit_business_rules_success(self) -> None:
        """Test submitting business rules successfully."""
        mock_request = AsyncMock(return_value={"result": {"sys_id": "rule_123"}})

        payloads = [
            {"name": "test_rule", "collection": "incident"},
            {"name": "test_rule (delete)", "collection": "incident"},
        ]

        await submit_business_rules(
            mock_request,
            "https://test.service-now.com/api/now/table",
            "test_rule",
            payloads,
        )

        assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_create_business_rule_if_not_exists_skips_existing(self) -> None:
        """Test that existing business rules are skipped."""
        mock_request = AsyncMock(return_value={"result": [{"sys_id": "existing_rule"}]})

        await create_business_rule_if_not_exists(
            mock_request,
            "https://test.service-now.com/api/now/table",
            REST_MESSAGE_NAME,
            "incident",
            ["sys_id", "number"],
        )

        assert mock_request.call_count == 1

    @pytest.mark.asyncio
    async def test_create_business_rule_if_not_exists_creates_rules(self) -> None:
        """Test creating new business rules."""
        mock_request = AsyncMock(
            side_effect=[
                {"result": []},
                {"result": {"sys_id": "upsert_rule_id"}},
                {"result": {"sys_id": "delete_rule_id"}},
            ]
        )

        await create_business_rule_if_not_exists(
            mock_request,
            "https://test.service-now.com/api/now/table",
            REST_MESSAGE_NAME,
            "incident",
            ["sys_id", "number"],
        )

        assert mock_request.call_count == 3
