"""Tests for `_AwsAbstractWebhookProcessor` auth, validation, and allowlist."""

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aws.webhook.webhook_processors.aws_abstract_webhook_processor import (
    _AwsAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


_VALID_ENVELOPE: Dict[str, Any] = {
    "source": "aws.ec2",
    "detail-type": "EC2 Instance State-change Notification",
    "detail": {"instance-id": "i-1234567890abcdef0", "state": "running"},
    "account": "123456789012",
    "region": "us-east-1",
}


class _StubProcessor(_AwsAbstractWebhookProcessor):
    """Minimal concrete processor used purely to exercise the base contract."""

    def __init__(self, event: WebhookEvent, matches: bool = True) -> None:
        super().__init__(event=event)
        self._matches = matches

    async def _matches_event(self, event: WebhookEvent) -> bool:
        return self._matches

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return []

    async def handle_event(self, payload: Any, resource: Any) -> Any:
        raise NotImplementedError


def _make_event(
    payload: Dict[str, Any] | None = None, headers: Dict[str, str] | None = None
) -> WebhookEvent:
    return WebhookEvent(
        trace_id="trace-1",
        payload=payload if payload is not None else dict(_VALID_ENVELOPE),
        headers=headers if headers is not None else {},
    )


def _patch_integration_config(config: Dict[str, Any]) -> Any:
    mock_ocean = MagicMock()
    mock_ocean.integration_config = config
    return patch(
        "aws.webhook.webhook_processors.aws_abstract_webhook_processor.ocean",
        mock_ocean,
    )


class TestAuthenticate:
    @pytest.mark.asyncio
    async def test_returns_true_for_matching_bearer(self) -> None:
        event = _make_event()
        processor = _StubProcessor(event=event)

        with _patch_integration_config({"webhook_secret": "shh"}):
            assert (
                await processor.authenticate(
                    payload={}, headers={"Authorization": "Bearer shh"}
                )
                is True
            )

    @pytest.mark.asyncio
    async def test_returns_false_for_wrong_bearer(self) -> None:
        event = _make_event()
        processor = _StubProcessor(event=event)

        with _patch_integration_config({"webhook_secret": "shh"}):
            assert (
                await processor.authenticate(
                    payload={}, headers={"Authorization": "Bearer wrong"}
                )
                is False
            )

    @pytest.mark.asyncio
    async def test_returns_false_for_missing_authorization(self) -> None:
        event = _make_event()
        processor = _StubProcessor(event=event)

        with _patch_integration_config({"webhook_secret": "shh"}):
            assert await processor.authenticate(payload={}, headers={}) is False

    @pytest.mark.asyncio
    async def test_returns_false_when_secret_not_configured(self) -> None:
        event = _make_event()
        processor = _StubProcessor(event=event)

        with _patch_integration_config({}):
            assert (
                await processor.authenticate(
                    payload={}, headers={"Authorization": "Bearer anything"}
                )
                is False
            )


class TestValidatePayload:
    @pytest.mark.asyncio
    async def test_accepts_valid_eventbridge_envelope(self) -> None:
        event = _make_event()
        processor = _StubProcessor(event=event)

        assert await processor.validate_payload(_VALID_ENVELOPE) is True

    @pytest.mark.asyncio
    async def test_rejects_missing_required_field(self) -> None:
        payload = dict(_VALID_ENVELOPE)
        del payload["account"]
        event = _make_event(payload=payload)
        processor = _StubProcessor(event=event)

        assert await processor.validate_payload(payload) is False

    @pytest.mark.asyncio
    async def test_rejects_non_object_detail(self) -> None:
        payload = dict(_VALID_ENVELOPE)
        payload["detail"] = "not-an-object"
        event = _make_event(payload=payload)
        processor = _StubProcessor(event=event)

        assert await processor.validate_payload(payload) is False


class TestShouldProcessEvent:
    @pytest.mark.asyncio
    async def test_drops_event_when_processor_does_not_match(self) -> None:
        event = _make_event()
        processor = _StubProcessor(event=event, matches=False)

        with _patch_integration_config({"allowed_account_ids": ["123456789012"]}):
            assert await processor.should_process_event(event) is False

    @pytest.mark.asyncio
    async def test_drops_event_when_account_id_missing(self) -> None:
        payload = dict(_VALID_ENVELOPE)
        del payload["account"]
        event = _make_event(payload=payload)
        processor = _StubProcessor(event=event)

        with _patch_integration_config({"allowed_account_ids": ["123456789012"]}):
            assert await processor.should_process_event(event) is False

    @pytest.mark.asyncio
    async def test_passes_when_account_is_in_explicit_allowlist(self) -> None:
        event = _make_event()
        processor = _StubProcessor(event=event)

        with _patch_integration_config({"allowed_account_ids": ["123456789012"]}):
            assert await processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_drops_when_account_not_in_explicit_allowlist(self) -> None:
        event = _make_event()
        processor = _StubProcessor(event=event)

        with _patch_integration_config({"allowed_account_ids": ["999999999999"]}):
            assert await processor.should_process_event(event) is False

    @pytest.mark.asyncio
    async def test_routing_does_not_call_discover_when_allowlist_unset(self) -> None:
        """Processor selection runs before auth; must not touch AWS/session discovery."""
        event = _make_event()
        processor = _StubProcessor(event=event)
        mock_discover = AsyncMock(return_value={"123456789012"})

        with _patch_integration_config({}):
            with patch(
                "aws.auth.session_factory.discover_valid_account_ids",
                mock_discover,
            ):
                assert await processor.should_process_event(event) is True
        mock_discover.assert_not_called()

    @pytest.mark.asyncio
    async def test_enforce_drops_when_derived_allowlist_excludes_account(self) -> None:
        event = _make_event()
        processor = _StubProcessor(event=event)

        with _patch_integration_config({}):
            with patch(
                "aws.auth.session_factory.discover_valid_account_ids",
                new=AsyncMock(return_value={"999999999999"}),
            ):
                assert (
                    await processor._is_account_allowed("123456789012", phase="enforce")
                    is False
                )

    @pytest.mark.asyncio
    async def test_enforce_falls_through_when_no_accounts_validated_yet(self) -> None:
        """Empty derived set means no filter yet — same as before, after auth."""
        event = _make_event()
        processor = _StubProcessor(event=event)

        with _patch_integration_config({}):
            with patch(
                "aws.auth.session_factory.discover_valid_account_ids",
                new=AsyncMock(return_value=set()),
            ):
                assert (
                    await processor._is_account_allowed("123456789012", phase="enforce")
                    is True
                )
