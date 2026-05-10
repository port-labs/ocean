"""Tests for AWSWebhookProcessor (handler.py) — routing, auth, and resilience."""
import base64
import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEventRawResults,
)

import aws.live_events.handler as handler_module
from aws.live_events.handler import AWSWebhookProcessor
from tests.live_events.conftest import (
    make_eventbridge_event,
    make_sns_envelope,
    make_webhook_event,
    sign_body,
)


WEBHOOK_SECRET = "test-secret-abc123"

_EC2_DETAIL_TYPE = "EC2 Instance State-change Notification"
_LAMBDA_DETAIL_TYPE = "AWS API Call via CloudTrail"
_UNKNOWN_DETAIL_TYPE = "Some Unknown AWS Service Event"


def _resource_config(kind: str = "AWS::EC2::Instance") -> ResourceConfig:
    return ResourceConfig(
        kind=kind,
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".id",
                    blueprint=f'"{kind}"',
                    properties={},
                    relations={},
                )
            )
        ),
    )


def _make_processor(payload: dict[str, Any], secret: str | None = None) -> AWSWebhookProcessor:
    raw = json.dumps(payload).encode()
    headers: dict[str, str] = {}
    if secret:
        headers["x-hub-signature-256"] = sign_body(raw, secret)
    event = make_webhook_event(payload, headers=headers, raw_body=raw)
    return AWSWebhookProcessor(event)


@contextmanager
def _mock_ocean_secret(secret: str | None) -> Generator[None, None, None]:
    """Patch ocean in the handler module so integration_config returns a plain dict."""
    mock_ocean = MagicMock()
    mock_ocean.integration_config = {"webhook_secret": secret}
    with patch.object(handler_module, "ocean", mock_ocean):
        yield


def _generate_test_certificate() -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "sns.us-east-1.amazonaws.com")]
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )
    return private_key, certificate


def _sign_sns_payload(
    payload: dict[str, Any], private_key: rsa.RSAPrivateKey, signature_version: str = "1"
) -> str:
    algorithm = hashes.SHA1() if signature_version == "1" else hashes.SHA256()
    string_to_sign = handler_module._build_sns_string_to_sign(payload).encode("utf-8")
    return base64.b64encode(
        private_key.sign(string_to_sign, padding.PKCS1v15(), algorithm)
    ).decode("utf-8")



class TestValidatePayload:
    @pytest.mark.asyncio
    async def test_notification_with_message_is_valid(self) -> None:
        payload = {"Type": "Notification", "Message": '{"detail-type": "test"}'}
        proc = _make_processor(payload)
        assert await proc.validate_payload(payload) is True

    @pytest.mark.asyncio
    async def test_subscription_confirmation_is_valid(self) -> None:
        payload = {"Type": "SubscriptionConfirmation", "SubscribeURL": "https://example.com"}
        proc = _make_processor(payload)
        assert await proc.validate_payload(payload) is True

    @pytest.mark.asyncio
    async def test_missing_type_is_invalid(self) -> None:
        payload = {"Message": "hello"}
        proc = _make_processor(payload)
        assert await proc.validate_payload(payload) is False

    @pytest.mark.asyncio
    async def test_unknown_type_is_invalid(self) -> None:
        payload = {"Type": "UnsubscribeConfirmation", "Message": "test"}
        proc = _make_processor(payload)
        assert await proc.validate_payload(payload) is False

    @pytest.mark.asyncio
    async def test_notification_without_message_is_invalid(self) -> None:
        payload = {"Type": "Notification"}
        proc = _make_processor(payload)
        assert await proc.validate_payload(payload) is False



class TestInvalidSignature:
    """Security: requests with invalid or missing signatures must be rejected."""

    @pytest.mark.asyncio
    async def test_missing_signature_header_rejected(self) -> None:
        with _mock_ocean_secret(WEBHOOK_SECRET):
            eb_event = make_eventbridge_event(_EC2_DETAIL_TYPE, {"instance-id": "i-1", "state": "running"})
            sns_payload = make_sns_envelope(eb_event)
            raw = json.dumps(sns_payload).encode()
            event = make_webhook_event(sns_payload, headers={}, raw_body=raw)
            proc = AWSWebhookProcessor(event)
            result = await proc.should_process_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_wrong_signature_header_rejected(self) -> None:
        with _mock_ocean_secret(WEBHOOK_SECRET):
            eb_event = make_eventbridge_event(_EC2_DETAIL_TYPE, {"instance-id": "i-1", "state": "running"})
            sns_payload = make_sns_envelope(eb_event)
            raw = json.dumps(sns_payload).encode()
            event = make_webhook_event(
                sns_payload,
                headers={"x-hub-signature-256": "sha256=deadbeef"},
                raw_body=raw,
            )
            proc = AWSWebhookProcessor(event)
            result = await proc.should_process_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_valid_signature_accepted(self) -> None:
        with _mock_ocean_secret(WEBHOOK_SECRET):
            eb_event = make_eventbridge_event(_EC2_DETAIL_TYPE, {"instance-id": "i-1", "state": "running"})
            sns_payload = make_sns_envelope(eb_event)
            raw = json.dumps(sns_payload).encode()
            sig = sign_body(raw, WEBHOOK_SECRET)
            event = make_webhook_event(
                sns_payload,
                headers={"x-hub-signature-256": sig},
                raw_body=raw,
            )
            proc = AWSWebhookProcessor(event)
            result = await proc.should_process_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_no_secret_configured_passes_through(self) -> None:
        """When no secret is configured, direct SNS deliveries must validate natively."""
        with _mock_ocean_secret(None):
            private_key, certificate = _generate_test_certificate()
            eb_event = make_eventbridge_event(_EC2_DETAIL_TYPE, {"instance-id": "i-1", "state": "running"})
            sns_payload = make_sns_envelope(eb_event)
            sns_payload["Signature"] = _sign_sns_payload(sns_payload, private_key)
            event = make_webhook_event(sns_payload)
            proc = AWSWebhookProcessor(event)
            with patch.object(
                handler_module,
                "_load_sns_signing_certificate",
                return_value=certificate,
            ):
                result = await proc.should_process_event(event)
        assert result is True

    @pytest.mark.asyncio
    async def test_no_secret_invalid_sns_signature_rejected(self) -> None:
        with _mock_ocean_secret(None):
            eb_event = make_eventbridge_event(_EC2_DETAIL_TYPE, {"instance-id": "i-1", "state": "running"})
            sns_payload = make_sns_envelope(eb_event)
            sns_payload["Signature"] = "not-base64"
            event = make_webhook_event(sns_payload)
            proc = AWSWebhookProcessor(event)
            result = await proc.should_process_event(event)
        assert result is False



class TestValidEventRouting:
    """Valid event routing: should_process_event returns True for known kinds."""

    @pytest.mark.asyncio
    async def test_ec2_event_routed(self) -> None:
        with _mock_ocean_secret(None):
            eb_event = make_eventbridge_event(
                _EC2_DETAIL_TYPE,
                {"instance-id": "i-abc", "state": "running"},
            )
            sns_payload = make_sns_envelope(eb_event)
            event = make_webhook_event(sns_payload)
            proc = AWSWebhookProcessor(event)
            with patch.object(proc, "_verify_sns_signature", return_value=True):
                assert await proc.should_process_event(event) is True
                kinds = await proc.get_matching_kinds(event)
        assert "AWS::EC2::Instance" in kinds

    @pytest.mark.asyncio
    async def test_ecs_deployment_event_routed(self) -> None:
        with _mock_ocean_secret(None):
            detail = {
                "clusterArn": "arn:aws:ecs:us-east-1:123456789012:cluster/my-cluster",
                "serviceArn": "arn:aws:ecs:us-east-1:123456789012:service/my-cluster/my-service",
            }
            eb_event = make_eventbridge_event("ECS Deployment State Change", detail, source="aws.ecs")
            sns_payload = make_sns_envelope(eb_event)
            event = make_webhook_event(sns_payload)
            proc = AWSWebhookProcessor(event)
            with patch.object(proc, "_verify_sns_signature", return_value=True):
                assert await proc.should_process_event(event) is True
                kinds = await proc.get_matching_kinds(event)
        assert "AWS::ECS::Service" in kinds

    @pytest.mark.asyncio
    async def test_lambda_cloudtrail_event_routed(self) -> None:
        with _mock_ocean_secret(None):
            detail = {
                "eventSource": "lambda.amazonaws.com",
                "eventName": "UpdateFunctionCode20150331v2",
                "requestParameters": {"functionName": "my-func"},
            }
            eb_event = make_eventbridge_event(_LAMBDA_DETAIL_TYPE, detail, source="aws.cloudtrail")
            sns_payload = make_sns_envelope(eb_event)
            event = make_webhook_event(sns_payload)
            proc = AWSWebhookProcessor(event)
            with patch.object(proc, "_verify_sns_signature", return_value=True):
                assert await proc.should_process_event(event) is True
                kinds = await proc.get_matching_kinds(event)
        assert "AWS::Lambda::Function" in kinds

    @pytest.mark.asyncio
    async def test_s3_cloudtrail_event_routed(self) -> None:
        with _mock_ocean_secret(None):
            detail = {
                "eventSource": "s3.amazonaws.com",
                "eventName": "CreateBucket",
                "requestParameters": {"bucketName": "my-bucket"},
            }
            eb_event = make_eventbridge_event(_LAMBDA_DETAIL_TYPE, detail, source="aws.cloudtrail")
            sns_payload = make_sns_envelope(eb_event)
            event = make_webhook_event(sns_payload)
            proc = AWSWebhookProcessor(event)
            with patch.object(proc, "_verify_sns_signature", return_value=True):
                assert await proc.should_process_event(event) is True
                kinds = await proc.get_matching_kinds(event)
        assert "AWS::S3::Bucket" in kinds


class TestUnknownEvent:
    """Resilience: unknown event types must be logged and safely skipped."""

    @pytest.mark.asyncio
    async def test_unknown_detail_type_skipped(self) -> None:
        with _mock_ocean_secret(None):
            eb_event = make_eventbridge_event(_UNKNOWN_DETAIL_TYPE, {"some": "data"})
            sns_payload = make_sns_envelope(eb_event)
            event = make_webhook_event(sns_payload)
            proc = AWSWebhookProcessor(event)
            with patch.object(proc, "_verify_sns_signature", return_value=True):
                result = await proc.should_process_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_unknown_cloudtrail_source_skipped(self) -> None:
        with _mock_ocean_secret(None):
            detail = {
                "eventSource": "rds.amazonaws.com",
                "eventName": "CreateDBInstance",
                "requestParameters": {"dBInstanceIdentifier": "db-1"},
            }
            eb_event = make_eventbridge_event(_LAMBDA_DETAIL_TYPE, detail, source="aws.cloudtrail")
            sns_payload = make_sns_envelope(eb_event)
            event = make_webhook_event(sns_payload)
            proc = AWSWebhookProcessor(event)
            with patch.object(proc, "_verify_sns_signature", return_value=True):
                result = await proc.should_process_event(event)
        assert result is False

    @pytest.mark.asyncio
    async def test_subscription_confirmation_not_processed(self) -> None:
        with _mock_ocean_secret(None):
            payload = {
                "Type": "SubscriptionConfirmation",
                "TopicArn": "arn:aws:sns:us-east-1:123456789012:port-ocean-live-events",
                "SubscribeURL": "https://sns.amazonaws.com/confirm",
            }
            event = make_webhook_event(payload)
            proc = AWSWebhookProcessor(event)
            with patch.object(proc, "_verify_sns_signature", return_value=True):
                result = await proc.should_process_event(event)
        assert result is False



class TestDuplicateEvent:
    """Idempotency: processing the same event twice yields the same result."""

    @pytest.mark.asyncio
    async def test_duplicate_event_same_result(self) -> None:
        fake_resource = {
            "Type": "AWS::EC2::Instance",
            "Properties": {"InstanceId": "i-dup", "State": {"Name": "running"}},
        }

        async def mock_sessions():
            from aws.auth.session_factory import AccountInfo
            from aiobotocore.session import AioSession
            yield AccountInfo(Id="123456789012", Name="test"), MagicMock(spec=AioSession)

        with _mock_ocean_secret(None):
            with patch.object(handler_module, "get_all_account_sessions", mock_sessions):
                with patch("aws.live_events.processors.ec2.EC2InstanceExporter") as MockExporter:
                    MockExporter.return_value.get_resource = AsyncMock(return_value=fake_resource)

                    eb_event = make_eventbridge_event(
                        _EC2_DETAIL_TYPE,
                        {"instance-id": "i-dup", "state": "running"},
                    )
                    sns_payload = make_sns_envelope(eb_event)
                    event = make_webhook_event(sns_payload)
                    proc = AWSWebhookProcessor(event)
                    resource = _resource_config("AWS::EC2::Instance")

                    result1 = await proc.handle_event(sns_payload, resource)
                    result2 = await proc.handle_event(sns_payload, resource)

        assert result1.updated_raw_results == result2.updated_raw_results
        assert result1.deleted_raw_results == result2.deleted_raw_results
