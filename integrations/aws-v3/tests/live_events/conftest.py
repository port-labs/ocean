"""Shared fixtures for live events tests."""
import hashlib
import hmac
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiobotocore.session import AioSession
from fastapi import Request
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from aws.auth.session_factory import AccountInfo



def make_eventbridge_event(
    detail_type: str,
    detail: dict[str, Any],
    account: str = "123456789012",
    region: str = "us-east-1",
    source: str = "aws.ec2",
) -> dict[str, Any]:
    """Build a minimal EventBridge event envelope."""
    return {
        "version": "0",
        "id": "test-event-id",
        "source": source,
        "account": account,
        "time": "2026-05-09T00:00:00Z",
        "region": region,
        "detail-type": detail_type,
        "detail": detail,
    }


def make_sns_envelope(
    eb_event: dict[str, Any],
    sns_type: str = "Notification",
    topic_arn: str = "arn:aws:sns:us-east-1:123456789012:port-ocean-live-events",
) -> dict[str, Any]:
    """Wrap an EventBridge event in an SNS notification envelope."""
    return {
        "Type": sns_type,
        "MessageId": "test-message-id",
        "TopicArn": topic_arn,
        "Message": json.dumps(eb_event),
        "Timestamp": "2026-05-09T00:00:00.000Z",
        "SignatureVersion": "1",
        "Signature": "FAKESIGNATURE==",
        "SigningCertURL": "https://sns.us-east-1.amazonaws.com/SimpleNotificationService.pem",
    }


def make_webhook_event(
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    raw_body: bytes | None = None,
) -> WebhookEvent:
    """Build a WebhookEvent, optionally with a mock original_request."""
    if raw_body is not None:
        mock_request = MagicMock()  # No spec — avoids falsy-via-__len__ from starlette Request
        mock_request.headers = headers or {}

        async def _body() -> bytes:
            return raw_body

        mock_request.body = _body
    else:
        mock_request = None

    event = WebhookEvent(
        trace_id="test-trace",
        payload=payload,
        headers=headers or {},
        original_request=mock_request,
    )
    return event


def sign_body(body: bytes, secret: str) -> str:
    """Compute sha256=<hex> HMAC signature for the given body and secret."""
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()



@pytest.fixture
def mock_session() -> AioSession:
    return MagicMock(spec=AioSession)


@pytest.fixture
def mock_account_info() -> AccountInfo:
    return AccountInfo(Id="123456789012", Name="test-account")


@pytest.fixture
def mock_aiosession_factory(
    mock_session: AioSession,
    mock_account_info: AccountInfo,
):
    """Returns an async generator that yields (account_info, session) once."""

    async def _gen():
        yield mock_account_info, mock_session

    return _gen
