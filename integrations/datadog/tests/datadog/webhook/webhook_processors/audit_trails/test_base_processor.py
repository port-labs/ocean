from typing import Any

import pytest

from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from datadog.webhook.webhook_processors.audit_trails.base_processor import BaseProcessor


class MockAuditTrailBaseProcessor(BaseProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[Any]:
        return []

    async def validate_payload(self, payload: dict[str, Any]) -> bool:
        return True

    async def handle_event(self, payload: dict[str, Any], resource_config: Any) -> Any:
        return None


@pytest.fixture
def processor() -> MockAuditTrailBaseProcessor:
    return MockAuditTrailBaseProcessor(
        WebhookEvent(trace_id="test", payload={}, headers={})
    )


def test_extract_wrapped_event_prefers_event_key() -> None:
    payload = {"event": {"asset": {"type": "monitor"}}}
    assert BaseProcessor._extract_wrapped_event(payload) == payload["event"]


def test_extract_asset_type_and_id_from_data_wrapper() -> None:
    payload = {"data": {"asset": {"type": "USER", "id": 123}}}
    assert BaseProcessor.extract_asset_type(payload) == "user"
    assert BaseProcessor.extract_asset_id(payload) == "123"


def test_is_delete_event_matches_supported_delete_tokens() -> None:
    assert BaseProcessor.is_delete_event({"action": "resource.delete"}) is True
    assert BaseProcessor.is_delete_event({"action": "member.remove"}) is True
    assert BaseProcessor.is_delete_event({"action": "object.destroy"}) is True
    assert BaseProcessor.is_delete_event({"action": "object.update"}) is False


@pytest.mark.asyncio
async def test_should_process_event_for_supported_and_unsupported_actions(
    processor: MockAuditTrailBaseProcessor,
) -> None:
    supported_event = WebhookEvent(
        trace_id="supported",
        payload={"action": "resource.assign"},
        headers={},
    )
    unsupported_event = WebhookEvent(
        trace_id="unsupported",
        payload={"action": "resource.read"},
        headers={},
    )
    missing_action_event = WebhookEvent(
        trace_id="missing",
        payload={},
        headers={},
    )

    assert await processor.should_process_event(supported_event) is True
    assert await processor.should_process_event(unsupported_event) is False
    assert await processor.should_process_event(missing_action_event) is False
