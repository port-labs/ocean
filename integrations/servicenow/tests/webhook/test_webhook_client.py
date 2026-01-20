import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from webhook.webhook_client import ServicenowWebhookClient
from tests.conftest import SAMPLE_INCIDENT_DATA
from typing import Dict, Any


class TestServicenowWebhookClient:
    """Test suite for ServiceNow webhook client."""

    def test_generate_business_rule_script_basic(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test generating a business rule script with basic fields."""
        fields = ["sys_id", "number", "state"]
        script = webhook_client._generate_business_rule_script(fields)

        assert "RESTMessageV2" in script
        assert webhook_client.REST_MESSAGE_NAME in script
        assert '"sys_id": current.sys_id + "",' in script
        assert '"number": current.number + "",' in script
        assert '"state": current.state + ""' in script

    def test_generate_business_rule_script_with_dot_fields(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test generating a business rule script with fields containing dots."""
        fields = ["caller_id.name", "assignment_group.name"]
        script = webhook_client._generate_business_rule_script(fields)

        # Dots should be replaced with underscores in the payload key
        assert '"caller_id_name": current.caller_id.name + "",' in script
        assert '"assignment_group_name": current.assignment_group.name + ""' in script

    def test_generate_business_rule_script_delete_event(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test generating a business rule script for delete events."""
        fields = ["sys_id", "number"]
        script = webhook_client._generate_business_rule_script(
            fields, delete_event=True
        )

        # Delete events should use 'previous' instead of 'current'
        assert "previous.sys_id" in script
        assert "previous.number" in script
        assert "current." not in script

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
    async def test_find_rest_message_found(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test finding an existing REST message."""
        mock_response = {"result": [{"sys_id": "rest_msg_123"}]}

        with patch.object(
            webhook_client, "_make_request", AsyncMock(return_value=mock_response)
        ):
            result = await webhook_client._find_rest_message("Ocean Port Outbound")

            assert result == "rest_msg_123"

    @pytest.mark.asyncio
    async def test_find_rest_message_not_found(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test when REST message does not exist."""
        mock_response: Dict[str, Any] = {"result": []}

        with patch.object(
            webhook_client, "_make_request", AsyncMock(return_value=mock_response)
        ):
            result = await webhook_client._find_rest_message("Nonexistent Message")

            assert result is None

    @pytest.mark.asyncio
    async def test_create_or_get_rest_message_existing(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test using an existing REST message."""
        with patch.object(
            webhook_client, "_find_rest_message", AsyncMock(return_value="existing_id")
        ):
            result = await webhook_client._create_or_get_rest_message(
                "https://example.com/webhook"
            )

            assert result == "existing_id"

    @pytest.mark.asyncio
    async def test_create_or_get_rest_message_create_new(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test creating a new REST message."""
        parent_response = {"result": {"sys_id": "new_parent_id"}}
        fn_response = {"result": {"sys_id": "new_fn_id"}}

        with patch.object(
            webhook_client, "_find_rest_message", AsyncMock(return_value=None)
        ):
            with patch.object(
                webhook_client,
                "_make_request",
                AsyncMock(side_effect=[parent_response, fn_response]),
            ):
                result = await webhook_client._create_or_get_rest_message(
                    "https://example.com/webhook"
                )

                assert result == "new_parent_id"

    @pytest.mark.asyncio
    async def test_create_or_get_rest_message_creation_failure(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test handling REST message creation failure."""
        with patch.object(
            webhook_client, "_find_rest_message", AsyncMock(return_value=None)
        ):
            with patch.object(
                webhook_client, "_make_request", AsyncMock(return_value=None)
            ):
                result = await webhook_client._create_or_get_rest_message(
                    "https://example.com/webhook"
                )

                assert result is None

    @pytest.mark.asyncio
    async def test_business_rule_exists_true(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test checking if a business rule exists."""
        mock_response = {"result": [{"sys_id": "rule_123"}]}

        with patch.object(
            webhook_client, "_make_request", AsyncMock(return_value=mock_response)
        ):
            result = await webhook_client._business_rule_exists(
                "incident to port", "incident"
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_business_rule_exists_false(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test checking when business rule does not exist."""
        mock_response: Dict[str, Any] = {"result": []}

        with patch.object(
            webhook_client, "_make_request", AsyncMock(return_value=mock_response)
        ):
            result = await webhook_client._business_rule_exists(
                "nonexistent rule", "incident"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_create_business_rule_if_not_exists_skips_existing(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test that existing business rules are skipped."""
        with patch.object(
            webhook_client, "_business_rule_exists", AsyncMock(return_value=True)
        ):
            with patch.object(
                webhook_client, "_make_request", AsyncMock()
            ) as mock_request:
                await webhook_client._create_business_rule_if_not_exists(
                    rest_message_sys_id="rest_123",
                    table_name="incident",
                    fields=["sys_id", "number"],
                )

                # Should not create new rules if they already exist
                mock_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_business_rule_if_not_exists_creates_rules(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test creating new business rules."""
        with patch.object(
            webhook_client, "_business_rule_exists", AsyncMock(return_value=False)
        ):
            with patch.object(
                webhook_client,
                "_make_request",
                AsyncMock(return_value={"result": {"sys_id": "rule_123"}}),
            ) as mock_request:
                await webhook_client._create_business_rule_if_not_exists(
                    rest_message_sys_id="rest_123",
                    table_name="incident",
                    fields=["sys_id", "number"],
                )

                # Should create both upsert and delete rules
                assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_create_webhook_success(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test successful webhook creation for valid tables."""
        with patch.object(
            webhook_client,
            "_create_or_get_rest_message",
            AsyncMock(return_value="rest_123"),
        ):
            with patch.object(
                webhook_client,
                "_create_business_rule_if_not_exists",
                AsyncMock(),
            ) as mock_create_rule:
                await webhook_client.create_webhook(
                    "https://example.com", ["incident", "sys_user_group"]
                )

                # Should create rules for both valid tables
                assert mock_create_rule.call_count == 2

    @pytest.mark.asyncio
    async def test_create_webhook_skips_unknown_tables(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test that unknown tables are skipped."""
        with patch.object(
            webhook_client,
            "_create_or_get_rest_message",
            AsyncMock(return_value="rest_123"),
        ):
            with patch.object(
                webhook_client,
                "_create_business_rule_if_not_exists",
                AsyncMock(),
            ) as mock_create_rule:
                await webhook_client.create_webhook(
                    "https://example.com", ["incident", "unknown_table"]
                )

                # Should only create rules for known table (incident)
                assert mock_create_rule.call_count == 1

    @pytest.mark.asyncio
    async def test_create_webhook_no_rest_message(
        self, webhook_client: ServicenowWebhookClient
    ) -> None:
        """Test handling when REST message creation fails."""
        with patch.object(
            webhook_client, "_create_or_get_rest_message", AsyncMock(return_value=None)
        ):
            with patch.object(
                webhook_client,
                "_create_business_rule_if_not_exists",
                AsyncMock(),
            ) as mock_create_rule:
                await webhook_client.create_webhook("https://example.com", ["incident"])

                # Should not create any rules if REST message fails
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
