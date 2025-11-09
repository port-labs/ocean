import hashlib
import hmac
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from webhook_processors.terraform_base_webhook_processor import (
    TerraformBaseWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from port_ocean.core.handlers.port_app_config.models import ResourceConfig


class ConcreteWebhookProcessor(TerraformBaseWebhookProcessor):
    """Concrete implementation for testing abstract base class."""

    async def get_matching_kinds(self: Any, event: WebhookEvent) -> list[str]:
        return ["test-kind"]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def handle_event(
        self, payload: dict[str, Any], resource_config: ResourceConfig
    ) -> MagicMock:
        return MagicMock()


@pytest.fixture
def webhook_processor() -> Any:
    mock_event = MagicMock(spec=WebhookEvent)
    return ConcreteWebhookProcessor(mock_event)


@pytest.fixture
def mock_webhook_event() -> Any:
    event = MagicMock(spec=WebhookEvent)
    event.payload = {
        "notifications": [{"trigger": "run:completed", "run_status": "applied"}],
        "run_id": "run-123",
        "workspace_id": "ws-123",
    }
    event.headers = {}
    event._original_request = None
    return event


class TestAuthenticate:
    @pytest.mark.asyncio
    async def test_authenticate_always_returns_true(
        self, webhook_processor: Any
    ) -> None:
        result = await webhook_processor.authenticate({}, {})
        assert result is True


class TestIsVerificationEvent:
    def test_is_verification_event_true(self, webhook_processor: Any) -> None:
        payload: dict[str, Any] = {
            "notifications": [
                {"trigger": "verification", "message": "Webhook verification"}
            ]
        }

        result = webhook_processor._is_verification_event(payload)

        assert result is True

    def test_is_verification_event_false_different_trigger(
        self, webhook_processor: Any
    ) -> None:
        payload: dict[str, Any] = {
            "notifications": [{"trigger": "run:completed", "run_status": "applied"}]
        }

        result = webhook_processor._is_verification_event(payload)

        assert result is False

    def test_is_verification_event_false_no_notifications(
        self, webhook_processor: Any
    ) -> None:
        payload: dict[str, Any] = {"run_id": "run-123"}

        result = webhook_processor._is_verification_event(payload)

        assert result is False

    def test_is_verification_event_false_empty_notifications(
        self, webhook_processor: Any
    ) -> None:
        payload: dict[str, Any] = {"notifications": []}

        result = webhook_processor._is_verification_event(payload)

        assert result is False

    def test_is_verification_event_false_invalid_structure(
        self, webhook_processor: Any
    ) -> None:
        payload: dict[str, Any] = {"notifications": "not-a-list"}

        result = webhook_processor._is_verification_event(payload)

        assert result is False


class TestVerifyWebhookSignature:
    @pytest.mark.asyncio
    async def test_verify_webhook_signature_success(
        self, webhook_processor: Any
    ) -> None:
        webhook_secret = "test-secret"
        body = b'{"test": "data"}'
        expected_signature = hmac.new(
            webhook_secret.encode("utf-8"), body, hashlib.sha512
        ).hexdigest()

        event = MagicMock()
        event.headers = {"x-tfe-notification-signature": expected_signature}
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=body)
        event._original_request = mock_request

        with patch(
            "webhook_processors.terraform_base_webhook_processor.ocean"
        ) as mock_ocean:
            mock_ocean.integration_config.get = MagicMock(return_value=webhook_secret)

            result = await webhook_processor._verify_webhook_signature(event)

            assert result is True

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_no_secret_configured(
        self, webhook_processor: Any
    ) -> None:
        event = MagicMock()
        event.headers = {}
        event._original_request = MagicMock()

        with patch(
            "webhook_processors.terraform_base_webhook_processor.ocean"
        ) as mock_ocean:
            mock_ocean.integration_config.get = MagicMock(return_value=None)

            result = await webhook_processor._verify_webhook_signature(event)

            assert result is True

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_invalid_signature(
        self, webhook_processor: Any
    ) -> None:
        webhook_secret = "test-secret"
        body = b'{"test": "data"}'
        invalid_signature = "invalid-signature"

        event = MagicMock()
        event.headers = {"x-tfe-notification-signature": invalid_signature}
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=body)
        event._original_request = mock_request

        with patch(
            "webhook_processors.terraform_base_webhook_processor.ocean"
        ) as mock_ocean:
            mock_ocean.integration_config.get = MagicMock(return_value=webhook_secret)

            result = await webhook_processor._verify_webhook_signature(event)

            assert result is False

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_no_request_body(
        self, webhook_processor: Any
    ) -> None:
        event = MagicMock()
        event.headers = {"x-tfe-notification-signature": "some-signature"}
        event._original_request = None

        with patch(
            "webhook_processors.terraform_base_webhook_processor.ocean"
        ) as mock_ocean:
            mock_ocean.integration_config.get = MagicMock(return_value="test-secret")

            result = await webhook_processor._verify_webhook_signature(event)

            assert result is False

    @pytest.mark.asyncio
    async def test_verify_webhook_signature_header_but_no_secret(
        self, webhook_processor: Any
    ) -> None:
        event = MagicMock()
        event.headers = {"x-tfe-notification-signature": "some-signature"}
        event._original_request = MagicMock()

        with patch(
            "webhook_processors.terraform_base_webhook_processor.ocean"
        ) as mock_ocean:
            mock_ocean.integration_config.get = MagicMock(return_value=None)

            result = await webhook_processor._verify_webhook_signature(event)

            assert result is False


class TestShouldProcessEvent:
    @pytest.mark.asyncio
    async def test_should_process_event_success(self, webhook_processor: Any) -> None:
        webhook_secret = "test-secret"
        body = b'{"test": "data"}'
        signature = hmac.new(
            webhook_secret.encode("utf-8"), body, hashlib.sha512
        ).hexdigest()

        event = MagicMock()
        event.payload = {
            "notifications": [{"trigger": "run:completed", "run_status": "applied"}],
            "run_id": "run-123",
            "workspace_id": "ws-123",
        }
        event.headers = {"x-tfe-notification-signature": signature}
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=body)
        event._original_request = mock_request

        with patch(
            "webhook_processors.terraform_base_webhook_processor.ocean"
        ) as mock_ocean:
            mock_ocean.integration_config.get = MagicMock(return_value=webhook_secret)

            result = await webhook_processor.should_process_event(event)

            assert result is True

    @pytest.mark.asyncio
    async def test_should_process_event_no_original_request(
        self, webhook_processor: Any
    ) -> None:
        event = MagicMock()
        event._original_request = None

        result = await webhook_processor.should_process_event(event)

        assert result is False

    @pytest.mark.asyncio
    async def test_should_process_event_verification_event(
        self, webhook_processor: Any
    ) -> None:
        event = MagicMock()
        event.payload = {
            "notifications": [{"trigger": "verification"}],
        }
        event.headers = {}
        event._original_request = MagicMock()

        with patch(
            "webhook_processors.terraform_base_webhook_processor.ocean"
        ) as mock_ocean:
            mock_ocean.integration_config.get = MagicMock(return_value=None)

            result = await webhook_processor.should_process_event(event)

            assert result is False

    @pytest.mark.asyncio
    async def test_should_process_event_failed_signature_verification(
        self, webhook_processor: Any
    ) -> None:
        event = MagicMock()
        event.payload = {
            "notifications": [{"trigger": "run:completed"}],
        }
        event.headers = {"x-tfe-notification-signature": "invalid"}
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=b"body")
        event._original_request = mock_request

        with patch(
            "webhook_processors.terraform_base_webhook_processor.ocean"
        ) as mock_ocean:
            mock_ocean.integration_config.get = MagicMock(return_value="secret")

            result = await webhook_processor.should_process_event(event)

            assert result is False


class TestValidatePayload:
    @pytest.mark.asyncio
    async def test_validate_payload_success(self, webhook_processor: Any) -> None:
        payload: dict[str, Any] = {
            "notifications": [{"trigger": "run:completed", "run_status": "applied"}],
            "run_id": "run-123",
            "workspace_id": "ws-123",
        }

        result = await webhook_processor.validate_payload(payload)

        assert result is True

    @pytest.mark.asyncio
    async def test_validate_payload_not_dict(self, webhook_processor: Any) -> None:
        payload = "not-a-dict"

        result = await webhook_processor.validate_payload(payload)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_payload_missing_notifications(
        self, webhook_processor: Any
    ) -> None:
        payload: dict[str, Any] = {
            "run_id": "run-123",
            "workspace_id": "ws-123",
        }

        result = await webhook_processor.validate_payload(payload)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_payload_empty_notifications(
        self, webhook_processor: Any
    ) -> None:
        payload: dict[str, Any] = {
            "notifications": [],
            "run_id": "run-123",
            "workspace_id": "ws-123",
        }

        result = await webhook_processor.validate_payload(payload)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_payload_invalid_notification_structure(
        self, webhook_processor: Any
    ) -> None:
        payload: dict[str, Any] = {
            "notifications": ["not-a-dict"],
            "run_id": "run-123",
            "workspace_id": "ws-123",
        }

        result = await webhook_processor.validate_payload(payload)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_payload_missing_trigger(
        self, webhook_processor: Any
    ) -> None:
        payload: dict[str, Any] = {
            "notifications": [{"run_status": "applied"}],
            "run_id": "run-123",
            "workspace_id": "ws-123",
        }

        result = await webhook_processor.validate_payload(payload)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_payload_missing_run_status(
        self, webhook_processor: Any
    ) -> None:
        payload: dict[str, Any] = {
            "notifications": [{"trigger": "run:completed"}],
            "run_id": "run-123",
            "workspace_id": "ws-123",
        }

        result = await webhook_processor.validate_payload(payload)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_payload_missing_run_id(
        self, webhook_processor: Any
    ) -> None:
        payload: dict[str, Any] = {
            "notifications": [{"trigger": "run:completed", "run_status": "applied"}],
            "workspace_id": "ws-123",
        }

        result = await webhook_processor.validate_payload(payload)

        assert result is False

    @pytest.mark.asyncio
    async def test_validate_payload_missing_workspace_id(
        self, webhook_processor: Any
    ) -> None:
        payload: dict[str, Any] = {
            "notifications": [{"trigger": "run:completed", "run_status": "applied"}],
            "run_id": "run-123",
        }

        result = await webhook_processor.validate_payload(payload)

        assert result is False
