from typing import Any

import pytest

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    WebhookEvent,
    WebhookEventRawResults,
)

from datadog.webhook.types import AuditTrailEvent
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

    async def _should_process(self, event: AuditTrailEvent) -> bool:
        return event.attributes.evt.name == "Stub" and event.attributes.asset.type == "stub"

    async def _handle_audit_event(
        self, event: AuditTrailEvent, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        return WebhookEventRawResults(
            updated_raw_results=[event.dict()], deleted_raw_results=[]
        )


@pytest.fixture
def processor() -> _StubProcessor:
    return _StubProcessor(WebhookEvent(trace_id="test", payload={}, headers={}))


def test_parse_event_normalizes_action_and_type() -> None:
    raw = {
        "attributes": {
            "evt": {"name": "  Monitor  "},
            "action": "MODIFIED",
            "asset": {"type": "MONITOR", "id": "m-1"},
        }
    }
    event = AuditTrailEvent.parse_obj(raw)
    assert event.attributes.evt.name == "Monitor"
    assert event.attributes.action == "modified"
    assert event.attributes.asset.type == "monitor"


def test_parse_event_missing_required_field_raises() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AuditTrailEvent.parse_obj({"attributes": {"evt": {"name": "X"}, "action": "created"}})


@pytest.mark.asyncio
async def test_should_process_event_matches_stub(processor: _StubProcessor) -> None:
    assert await processor.should_process_event(_event(_raw("Stub", "created", "stub"))) is True


@pytest.mark.asyncio
async def test_should_process_event_false_when_evt_name_mismatch(
    processor: _StubProcessor,
) -> None:
    assert await processor.should_process_event(_event(_raw("WrongName", "created", "stub"))) is False


@pytest.mark.asyncio
async def test_should_process_event_false_when_payload_unparseable(
    processor: _StubProcessor,
) -> None:
    assert await processor.should_process_event(
        WebhookEvent(trace_id="t", payload={"bad": "payload"}, headers={})
    ) is False


@pytest.mark.asyncio
async def test_should_process_event_false_when_payload_is_list(
    processor: _StubProcessor,
) -> None:
    assert await processor.should_process_event(
        WebhookEvent(trace_id="t", payload=[_raw("Stub", "created", "stub")], headers={})
    ) is False


@pytest.mark.asyncio
async def test_validate_payload_always_true(processor: _StubProcessor) -> None:
    assert await processor.validate_payload(_raw("Stub", "created", "stub", "s-1")) is True
    assert await processor.validate_payload({"whatever": "dict"}) is True


@pytest.mark.asyncio
async def test_handle_event_delegates_to_handle_audit_event(processor: _StubProcessor) -> None:
    raw = _raw("Stub", "created", "stub", "s-1")
    result = await processor.handle_event(raw, resource_config={})
    assert result.updated_raw_results[0]["attributes"]["asset"]["id"] == "s-1"
    assert result.deleted_raw_results == []
