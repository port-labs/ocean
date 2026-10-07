import base64
import json

from port_ocean.core.handlers.webhook.webhook_log_context import (
    build_added_to_queue_payload_log_fields,
    build_live_event_timestamp_log_fields,
    count_flat_attributes,
    extract_compact_headers,
    is_sensitive_header_name,
    pick_nested_fields,
    sanitize_headers_for_logging,
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
    assert count_flat_attributes(payload) == 500
    assert count_flat_attributes(payload, limit=201) == 201
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


def test_is_sensitive_header_name_detects_auth_and_signature() -> None:
    assert is_sensitive_header_name("Authorization")
    assert is_sensitive_header_name("x-hub-signature-256")
    assert not is_sensitive_header_name("x-github-event")


def test_sanitize_headers_for_logging_redacts_sensitive_headers() -> None:
    sanitized = sanitize_headers_for_logging(
        {
            "x-github-event": "push",
            "authorization": "Bearer secret",
            "x-hub-signature-256": "sha256=abc",
        }
    )
    assert sanitized["x-github-event"] == "push"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["x-hub-signature-256"] == "[REDACTED]"


def test_pick_nested_fields_copies_dot_paths() -> None:
    payload = {
        "action": "opened",
        "repository": {"full_name": "org/repo"},
        "unused": "value",
    }
    assert pick_nested_fields(payload, ("action", "repository.full_name")) == {
        "action": "opened",
        "repository": {"full_name": "org/repo"},
    }


def test_extract_compact_headers_uses_generic_delivery_and_event_patterns() -> None:
    headers = {
        "x-github-event": "pull_request",
        "x-github-delivery": "delivery-id",
        "x-atlassian-webhook-identifier": "123",
        "x-custom-vendor-event": "created",
        "authorization": "secret",
        "content-type": "application/json",
    }
    compact = extract_compact_headers(headers)
    assert compact == {
        "x-github-event": "pull_request",
        "x-github-delivery": "delivery-id",
        "x-atlassian-webhook-identifier": "123",
        "x-custom-vendor-event": "created",
    }


def test_build_live_event_timestamp_log_fields_compact_uses_extra_identifiers_only() -> (
    None
):
    fields = build_live_event_timestamp_log_fields(
        "Started Processing",
        {"secret": "data", "action": "opened"},
        {"x-github-event": "push"},
        trace_id="trace",
        log_full_payload=False,
        webhook_path="/webhook",
        extra_identifiers={"action": "opened"},
    )
    assert fields["headers"] == {"x-github-event": "push"}
    assert fields["payload"] == {"action": "opened"}
    assert "secret" not in fields["payload"]


def test_build_live_event_timestamp_log_fields_masks_full_payload() -> None:
    payload = {
        "action": "opened",
        "token": "AKIAIOSFODNN7EXAMPLE",
    }
    fields = build_live_event_timestamp_log_fields(
        "Started Processing",
        payload,
        {"x-github-event": "push"},
        trace_id="trace",
        log_full_payload=True,
        webhook_path="/webhook",
    )
    assert fields["payload"]["token"] == "[REDACTED]"


def test_build_live_event_timestamp_log_fields_finish_follows_same_rules_as_start() -> (
    None
):
    fields_compact = build_live_event_timestamp_log_fields(
        "Finished Processing Successfully",
        {"secret": "data"},
        {"x-github-event": "push", "authorization": "secret"},
        trace_id="trace",
        log_full_payload=False,
        webhook_path="/webhook",
        extra_identifiers={"action": "opened"},
    )
    assert fields_compact["payload"] == {"action": "opened"}
    assert fields_compact["headers"] == {"x-github-event": "push"}

    fields_full = build_live_event_timestamp_log_fields(
        "Finished Processing With Error",
        {"token": "AKIAIOSFODNN7EXAMPLE"},
        {"authorization": "Bearer secret"},
        trace_id="trace",
        log_full_payload=True,
        webhook_path="/webhook",
    )
    assert fields_full["headers"]["authorization"] == "[REDACTED]"
    assert fields_full["payload"]["token"] == "[REDACTED]"
