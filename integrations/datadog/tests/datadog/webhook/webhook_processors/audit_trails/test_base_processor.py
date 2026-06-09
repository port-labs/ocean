from typing import Any

import pytest

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.client import DatadogClient
from datadog.webhook.types import AuditTrailEvent
from datadog.webhook.webhook_processors.audit_trails.base_processor import (
    BaseAuditTrailProcessor,
)


def _raw(
    evt_name: str, action: str, asset_type: str, asset_id: str = "x-1"
) -> dict[str, Any]:
    return {
        "attributes": {
            "evt": {"name": evt_name},
            "action": action,
            "asset": {"type": asset_type, "id": asset_id},
        }
    }


def _event(payload: dict[str, Any]) -> WebhookEvent:
    return WebhookEvent(trace_id="t", payload=payload, headers={})


class _StubProcessor(BaseAuditTrailProcessor):
    async def get_matching_kinds(self, _: Any) -> list[str]:
        return ["stub"]

    async def _should_process(self, event: AuditTrailEvent) -> bool:
        return (
            event.attributes.evt.name == "Stub"
            and event.attributes.asset.type == "stub"
        )

    async def _fetch_resource(
        self,
        client: DatadogClient,
        event: AuditTrailEvent,
        resource_config: ResourceConfig,
    ) -> dict[str, Any] | None:
        return event.dict()


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
        AuditTrailEvent.parse_obj(
            {"attributes": {"evt": {"name": "X"}, "action": "created"}}
        )


@pytest.mark.asyncio
async def test_should_process_event_matches_stub(processor: _StubProcessor) -> None:
    assert (
        await processor.should_process_event(_event(_raw("Stub", "created", "stub")))
        is True
    )


@pytest.mark.asyncio
async def test_should_process_event_false_when_evt_name_mismatch(
    processor: _StubProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            _event(_raw("WrongName", "created", "stub"))
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_when_payload_unparseable(
    processor: _StubProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(trace_id="t", payload={"bad": "payload"}, headers={})
        )
        is False
    )


@pytest.mark.asyncio
async def test_should_process_event_false_when_payload_is_list(
    processor: _StubProcessor,
) -> None:
    assert (
        await processor.should_process_event(
            WebhookEvent(
                trace_id="t", payload=[_raw("Stub", "created", "stub")], headers={}  # type: ignore[arg-type]
            )
        )
        is False
    )


@pytest.mark.asyncio
async def test_validate_payload_always_true(processor: _StubProcessor) -> None:
    assert (
        await processor.validate_payload(_raw("Stub", "created", "stub", "s-1")) is True
    )
    assert await processor.validate_payload({"whatever": "dict"}) is True


@pytest.mark.asyncio
async def test_handle_event_delegates_to_fetch_resource(
    processor: _StubProcessor,
) -> None:
    raw = _raw("Stub", "created", "stub", "s-1")
    result = await processor.handle_event(raw, resource_config={})  # type: ignore[arg-type]
    assert result.updated_raw_results[0]["attributes"]["asset"]["id"] == "s-1"
    assert result.deleted_raw_results == []


# ---------------------------------------------------------------------------
# BaseAuditTrailProcessor shared delete-or-fetch behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_action_returns_asset_dict_without_fetching(
    processor: _StubProcessor,
) -> None:
    raw = _raw("Stub", "deleted", "stub", "s-99")
    result = await processor.handle_event(raw, resource_config={})  # type: ignore[arg-type]
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == [{"type": "stub", "id": "s-99", "name": None}]


@pytest.mark.asyncio
async def test_non_delete_action_returns_fetched_resource(
    processor: _StubProcessor,
) -> None:
    raw = _raw("Stub", "modified", "stub", "s-42")
    result = await processor.handle_event(raw, resource_config={})  # type: ignore[arg-type]
    assert result.updated_raw_results[0]["attributes"]["asset"]["id"] == "s-42"
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_non_delete_with_missing_resource_returns_empty(
    processor: _StubProcessor,
) -> None:
    async def _return_none(*_: Any) -> None:
        return None

    processor._fetch_resource = _return_none  # type: ignore[assignment]
    raw = _raw("Stub", "modified", "stub", "s-00")
    result = await processor.handle_event(raw, resource_config={})  # type: ignore[arg-type]
    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_deleted_result_none_bypasses_delete_branch(
    processor: _StubProcessor,
) -> None:
    """When _deleted_result returns None the processor re-fetches even on delete."""
    processor._deleted_result = lambda _: None  # type: ignore[assignment]
    raw = _raw("Stub", "deleted", "stub", "s-77")
    result = await processor.handle_event(raw, resource_config={})  # type: ignore[arg-type]
    # should fall through to _fetch_resource, not produce a deletion
    assert result.deleted_raw_results == []
    assert result.updated_raw_results[0]["attributes"]["asset"]["id"] == "s-77"
