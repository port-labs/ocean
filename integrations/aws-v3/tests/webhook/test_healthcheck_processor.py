"""Tests for `WebhookHealthcheckProcessor`."""

from unittest.mock import MagicMock

import pytest

from aws.webhook.webhook_processors.webhook_healthcheck_processor import (
    HEALTHCHECK_HEADER,
    WebhookHealthcheckProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)


def _make_event(headers: dict[str, str]) -> WebhookEvent:
    return WebhookEvent(trace_id="trace-1", payload={}, headers=headers)


class TestWebhookHealthcheckProcessor:
    @pytest.mark.asyncio
    async def test_should_process_event_when_header_present(self) -> None:
        event = _make_event({HEALTHCHECK_HEADER: "1"})
        processor = WebhookHealthcheckProcessor(event=event)

        assert await processor.should_process_event(event) is True

    @pytest.mark.asyncio
    async def test_should_not_process_event_when_header_missing(self) -> None:
        event = _make_event({})
        processor = WebhookHealthcheckProcessor(event=event)

        assert await processor.should_process_event(event) is False

    @pytest.mark.asyncio
    async def test_should_not_process_event_with_wrong_header_value(self) -> None:
        event = _make_event({HEALTHCHECK_HEADER: "0"})
        processor = WebhookHealthcheckProcessor(event=event)

        assert await processor.should_process_event(event) is False

    @pytest.mark.asyncio
    async def test_authenticate_returns_true(self) -> None:
        event = _make_event({HEALTHCHECK_HEADER: "1"})
        processor = WebhookHealthcheckProcessor(event=event)

        assert await processor.authenticate(payload={}, headers={}) is True

    @pytest.mark.asyncio
    async def test_validate_payload_returns_true(self) -> None:
        event = _make_event({HEALTHCHECK_HEADER: "1"})
        processor = WebhookHealthcheckProcessor(event=event)

        assert await processor.validate_payload(payload={}) is True

    @pytest.mark.asyncio
    async def test_get_matching_kinds_returns_empty(self) -> None:
        event = _make_event({HEALTHCHECK_HEADER: "1"})
        processor = WebhookHealthcheckProcessor(event=event)

        assert await processor.get_matching_kinds(event) == []

    @pytest.mark.asyncio
    async def test_handle_event_returns_empty_results(self) -> None:
        event = _make_event({HEALTHCHECK_HEADER: "1"})
        processor = WebhookHealthcheckProcessor(event=event)

        result = await processor.handle_event(payload={}, resource_config=MagicMock())

        assert isinstance(result, WebhookEventRawResults)
        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
