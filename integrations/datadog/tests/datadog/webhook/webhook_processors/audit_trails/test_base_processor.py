from typing import Any

import pytest

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    AuditTrailEvent,
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

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not isinstance(event.payload, dict):
            return False
        e = self.parse_event(event.payload)
        return e.attributes.evt.name == "Stub" and e.attributes.asset is not None and e.attributes.asset.type == "stub"

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(updated_raw_results=[payload], deleted_raw_results=[])


@pytest.fixture
def processor() -> _StubProcessor:
    return _StubProcessor(WebhookEvent(trace_id="test", payload={}, headers={}))


def test_parse_event_normalizes_action_and_type() -> None:
    raw = {"attributes": {"evt": {"name": "  Monitor  "}, "action": "MODIFIED", "asset": {"type": "MONITOR", "id": "m-1"}}}
    event = AuditTrailEvent.parse_obj(raw)
    assert event.attributes.evt.name == "Monitor"
    assert event.attributes.action == "modified"
    assert event.attributes.asset is not None
    assert event.attributes.asset.type == "monitor"


def test_parse_event_missing_attributes_gives_defaults() -> None:
    event = AuditTrailEvent.parse_obj({})
    assert event.attributes.evt.name == ""
    assert event.attributes.action == ""
    assert event.attributes.asset is None


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
async def test_validate_payload_true_when_asset_id_present(processor: _StubProcessor) -> None:
    assert await processor.validate_payload(_raw("Stub", "created", "stub", "s-1")) is True


@pytest.mark.asyncio
async def test_validate_payload_false_when_no_asset_id(processor: _StubProcessor) -> None:
    assert await processor.validate_payload(
        {"attributes": {"evt": {"name": "Stub"}, "action": "created", "asset": {"type": "stub"}}}
    ) is False


@pytest.mark.asyncio
async def test_validate_payload_false_when_no_asset(processor: _StubProcessor) -> None:
    assert await processor.validate_payload(
        {"attributes": {"evt": {"name": "Stub"}, "action": "created"}}
    ) is False


@pytest.mark.asyncio
async def test_validate_payload_false_when_not_a_dict(processor: _StubProcessor) -> None:
    assert await processor.validate_payload([]) is False  # type: ignore[arg-type]
