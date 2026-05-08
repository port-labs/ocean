import json
import pytest
from unittest.mock import AsyncMock, patch
from typing import Any

from aws.live_events.webhook.router import route_event, route_sns_notification


# ── Router tests ─────────────────────────────────────────────────────────────

class TestEventRouter:

    @pytest.fixture
    def mock_session(self) -> AsyncMock:
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_ec2_event_routed_to_ec2_handler(
        self, mock_session: AsyncMock
    ) -> None:
        """EC2 state-change events must route to EC2InstanceLiveEventHandler."""
        event: dict[str, Any] = {
            "source": "aws.ec2",
            "detail-type": "EC2 Instance State-change Notification",
            "account": "123456789012",
            "region": "us-east-1",
            "detail": {"instance-id": "i-abc", "state": "running"},
        }

        with patch(
            "aws.live_events.handlers.ec2.EC2InstanceLiveEventHandler.handle",
            new_callable=AsyncMock,
        ) as mock_handle:
            await route_event(event, mock_session)
            mock_handle.assert_called_once_with(event, "123456789012", "us-east-1")

    @pytest.mark.asyncio
    async def test_lambda_event_routed_correctly(
        self, mock_session: AsyncMock
    ) -> None:
        """Lambda CloudTrail events must route to LambdaFunctionLiveEventHandler."""
        event = {
            "source": "aws.lambda",
            "detail-type": "AWS API Call via CloudTrail",
            "account": "123456789012",
            "region": "us-east-1",
            "detail": {
                "eventName": "UpdateFunctionCode20150331v2",
                "requestParameters": {"functionName": "my-fn"},
            },
        }

        with patch(
            "aws.live_events.handlers.lambda_function.LambdaFunctionLiveEventHandler.handle",
            new_callable=AsyncMock,
        ) as mock_handle:
            await route_event(event, mock_session)
            mock_handle.assert_called_once_with(event, "123456789012", "us-east-1")

    @pytest.mark.asyncio
    async def test_unknown_event_discarded_without_error(
        self, mock_session: AsyncMock
    ) -> None:
        """Events with no registered handler should be silently discarded."""
        event = {
            "source": "aws.rds",
            "detail-type": "RDS DB Instance Event",
            "account": "123456789012",
            "region": "us-east-1",
            "detail": {},
        }
        # Should not raise
        await route_event(event, mock_session)

    @pytest.mark.asyncio
    @patch("aws.live_events.webhook.router.EC2InstanceLiveEventHandler")
    async def test_handler_exception_does_not_propagate(
        self, mock_handler_cls: MagicMock, mock_session: AsyncMock
    ) -> None:
        """If a handler raises, the router should catch and log, not crash."""
        mock_handler = AsyncMock()
        mock_handler_cls.return_value = mock_handler
        mock_handler.handle.side_effect = Exception("handler blew up")

        event = {
            "source": "aws.ec2",
            "detail-type": "EC2 Instance State-change Notification",
            "account": "123456789012",
            "region": "us-east-1",
            "detail": {"instance-id": "i-err", "state": "running"},
        }

        await route_event(event, mock_session)  # must not raise

    @pytest.mark.asyncio
    async def test_sns_notification_unwrapped_and_routed(
        self, mock_session: AsyncMock
    ) -> None:
        """route_sns_notification should unwrap the SNS Message and route the inner event."""
        inner_event: dict[str, Any] = {
            "source": "aws.ec2",
            "detail-type": "EC2 Instance State-change Notification",
            "account": "123456789012",
            "region": "us-east-1",
            "detail": {"instance-id": "i-sns", "state": "stopped"},
        }

        sns_message = {
            "Type": "Notification",
            "MessageId": "abc-123",
            "Message": json.dumps(inner_event),
        }

        with patch(
            "aws.live_events.handlers.ec2.EC2InstanceLiveEventHandler.handle",
            new_callable=AsyncMock,
        ) as mock_handle:
            await route_sns_notification(sns_message, mock_session)
            mock_handle.assert_called_once_with(inner_event, "123456789012", "us-east-1")

    @pytest.mark.asyncio
    async def test_sns_notification_empty_message_skipped(
        self, mock_session: AsyncMock
    ) -> None:
        """SNS notifications with an empty Message field should be skipped without error."""
        sns_message = {"Type": "Notification", "MessageId": "x", "Message": ""}
        await route_sns_notification(sns_message, mock_session)  # must not raise

    @pytest.mark.asyncio
    async def test_sns_notification_invalid_json_message_skipped(
        self, mock_session: AsyncMock
    ) -> None:
        """SNS notifications with a non-JSON Message should be skipped without error."""
        sns_message = {"Type": "Notification", "MessageId": "x", "Message": "not-json"}
        await route_sns_notification(sns_message, mock_session)  # must not raise


# ── Signature validation tests ────────────────────────────────────────────────

class TestSNSSignatureValidation:

    @pytest.mark.asyncio
    @patch("aws.live_events.webhook.validator._fetch_certificate")
    async def test_invalid_cert_url_rejected(
        self, mock_fetch: AsyncMock
    ) -> None:
        """A certificate URL from outside amazonaws.com must be rejected."""
        from aws.live_events.webhook.validator import validate_sns_signature

        body = json.dumps({
            "Type": "Notification",
            "MessageId": "id-1",
            "Message": "{}",
            "Timestamp": "2026-01-01T00:00:00Z",
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:test",
            "SignatureVersion": "1",
            "Signature": "dGVzdA==",
            "SigningCertURL": "https://evil.com/cert.pem",
        }).encode()

        with pytest.raises(ValueError, match="certificate URL failed domain validation"):
            await validate_sns_signature(body)

        mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_json_body_rejected(self) -> None:
        """A non-JSON request body must be rejected."""
        from aws.live_events.webhook.validator import validate_sns_signature

        with pytest.raises(ValueError, match="Invalid JSON"):
            await validate_sns_signature(b"not-json")

    @pytest.mark.asyncio
    async def test_missing_signature_rejected(self) -> None:
        """A message without Signature or SigningCertURL must be rejected."""
        from aws.live_events.webhook.validator import validate_sns_signature

        body = json.dumps({"Type": "Notification", "MessageId": "id-1"}).encode()

        with pytest.raises(ValueError, match="missing SigningCertURL or Signature"):
            await validate_sns_signature(body)
