from typing import Any

import pytest

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)


def _raw(evt_name: str, action: str, asset_type: str, asset_id: str = "x-1") -> dict:
    return {
        "attributes": {
            "evt": {"name": evt_name},
            "action": action,
            "asset": {"type": asset_type, "id": asset_id},
        }
    }


def _event(payload: dict) -> WebhookEvent:
    return WebhookEvent(trace_id="t", payload=payload, headers={})


class _StubProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return ["stub"]

    def _matches(self, event: dict[str, Any]) -> bool:
        return (
            self.extract_evt_name(event) == "Stub"
            and self.extract_asset_type(event) == "stub"
        )

    async def should_process_event(self, event: WebhookEvent) -> bool:
        return isinstance(event.payload, dict) and self._matches(event.payload)

    async def validate_payload(self, payload: EventPayload) -> bool:
        return (
            isinstance(payload, dict)
            and self._matches(payload)
            and self.extract_asset_id(payload) is not None
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(updated_raw_results=[payload], deleted_raw_results=[])


@pytest.fixture
def processor() -> _StubProcessor:
    return _StubProcessor(WebhookEvent(trace_id="test", payload={}, headers={}))


def test_extract_evt_name_and_action() -> None:
    event = _raw("Monitor", "modified", "monitor", "m-1")
    assert BaseAuditTrailProcessor.extract_evt_name(event) == "Monitor"
    assert BaseAuditTrailProcessor.extract_action(event) == "modified"


def test_extract_asset_type_and_id_from_attributes() -> None:
    event = _raw("SLO", "created", "slo", "s-1")
    assert BaseAuditTrailProcessor.extract_asset_type(event) == "slo"
    assert BaseAuditTrailProcessor.extract_asset_id(event) == "s-1"


def test_is_delete_event_only_for_deleted_action() -> None:
    assert BaseAuditTrailProcessor.is_delete_event(_raw("X", "deleted", "x")) is True
    assert BaseAuditTrailProcessor.is_delete_event(_raw("X", "modified", "x")) is False
    assert BaseAuditTrailProcessor.is_delete_event(_raw("X", "created", "x")) is False


@pytest.mark.asyncio
async def test_should_process_event_matches_stub(processor: _StubProcessor) -> None:
    assert await processor.should_process_event(_event(_raw("Stub", "created", "stub"))) is True


@pytest.mark.asyncio
async def test_should_process_event_false_when_evt_name_mismatch(
    processor: _StubProcessor,
) -> None:
    assert await processor.should_process_event(_event(_raw("WrongName", "created", "stub"))) is False


@pytest.mark.asyncio
async def test_should_process_event_false_when_payload_is_list(
    processor: _StubProcessor,
) -> None:
    assert await processor.should_process_event(
        WebhookEvent(trace_id="t", payload=[_raw("Stub", "created", "stub")], headers={})
    ) is False


@pytest.mark.asyncio
async def test_handle_event_returns_result(processor: _StubProcessor) -> None:
    event = _raw("Stub", "created", "stub", "s-1")
    result = await processor.handle_event(event, resource_config={})
    assert result.updated_raw_results == [event]
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_validate_payload_true_for_matching_event_with_id(
    processor: _StubProcessor,
) -> None:
    assert await processor.validate_payload(_raw("Stub", "created", "stub", "s-1")) is True


@pytest.mark.asyncio
async def test_validate_payload_false_when_no_asset_id(processor: _StubProcessor) -> None:
    assert await processor.validate_payload(
        {"attributes": {"evt": {"name": "Stub"}, "action": "created", "asset": {"type": "stub"}}}
    ) is False


@pytest.mark.asyncio
async def test_validate_payload_false_when_event_not_matched(processor: _StubProcessor) -> None:
    assert await processor.validate_payload(_raw("Other", "created", "stub", "s-1")) is False
