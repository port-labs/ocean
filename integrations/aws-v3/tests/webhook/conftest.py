from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from aws.webhook.events import SNS_MESSAGE_TYPE_HEADER, SnsMessageType
from aws.webhook.processors import base as base_module


@pytest.fixture(autouse=True)
def reset_webhook_singletons() -> None:
    base_module._reset_singletons_for_tests()
    yield
    base_module._reset_singletons_for_tests()


@pytest.fixture
def stub_sns_verifier(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace the SNS signature verifier with one that accepts everything."""
    stub = MagicMock()
    stub.verify = AsyncMock(return_value=True)
    monkeypatch.setattr(base_module, "_get_sns_verifier", lambda: stub)
    return stub


@pytest.fixture
def reject_sns_verifier(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace the SNS signature verifier with one that rejects everything."""
    stub = MagicMock()
    stub.verify = AsyncMock(return_value=False)
    monkeypatch.setattr(base_module, "_get_sns_verifier", lambda: stub)
    return stub


@pytest.fixture
def stub_session_resolver(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Resolver that returns a fresh AsyncMock session for any account_id."""
    resolver = MagicMock()
    resolver.get = AsyncMock(side_effect=lambda account_id: AsyncMock(name=f"session-{account_id}"))
    monkeypatch.setattr(base_module, "_get_session_resolver", lambda: resolver)
    return resolver


@pytest.fixture
def no_session_resolver(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Resolver that returns None for any account — drives the unknown-account branch."""
    resolver = MagicMock()
    resolver.get = AsyncMock(return_value=None)
    monkeypatch.setattr(base_module, "_get_session_resolver", lambda: resolver)
    return resolver


def make_sns_notification(envelope: dict[str, Any], message_id: str = "mid-1") -> dict[str, Any]:
    """Wrap an EventBridge envelope in an SNS Notification."""
    return {
        "Type": SnsMessageType.NOTIFICATION.value,
        "MessageId": message_id,
        "TopicArn": "arn:aws:sns:us-east-1:111111111111:port-aws-v3-live-events",
        "Message": json.dumps(envelope),
        "Timestamp": "2026-05-14T12:00:00.000Z",
        "SignatureVersion": "1",
        "Signature": "fake-signature",
        "SigningCertURL": "https://sns.us-east-1.amazonaws.com/SimpleNotificationService.pem",
    }


def make_webhook_event(payload: dict[str, Any]) -> WebhookEvent:
    return WebhookEvent(
        trace_id="trace-1",
        payload=payload,
        headers={SNS_MESSAGE_TYPE_HEADER: SnsMessageType.NOTIFICATION.value},
    )
