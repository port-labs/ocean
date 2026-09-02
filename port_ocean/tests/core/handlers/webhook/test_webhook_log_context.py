import base64
import json

from port_ocean.core.handlers.webhook.webhook_log_context import (
    build_added_to_queue_payload_log_fields,
    count_flat_attributes,
)


def test_count_flat_attributes_counts_nested_leaves() -> None:
    payload = {"test": "data", "nested": {"value": 123}}
    assert count_flat_attributes(payload) == 2


def test_count_flat_attributes_counts_nested_list_leaves() -> None:
    payload = {"assignees": [{"login": "a"}, {"login": "b"}]}
    assert count_flat_attributes(payload) == 2
    assert len(payload) == 1


def test_count_flat_attributes_stops_once_limit_is_reached() -> None:
    payload = {f"key_{index}": index for index in range(500)}
    assert count_flat_attributes(payload) == 201
    assert count_flat_attributes(payload, limit=500) == 500


def test_build_added_to_queue_payload_log_fields_uses_json_for_small_payload() -> None:
    payload = {"test": "data", "nested": {"value": 123}}

    fields = build_added_to_queue_payload_log_fields(payload)

    assert fields == {"payload": payload}


def test_build_added_to_queue_payload_log_fields_uses_base64_for_large_payload() -> (
    None
):
    payload = {f"key_{index}": {"nested": index} for index in range(250)}

    fields = build_added_to_queue_payload_log_fields(payload)

    assert "payload" not in fields
    decoded = json.loads(base64.b64decode(fields["payload_b64"]))
    assert decoded == payload
