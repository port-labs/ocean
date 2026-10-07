import base64
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

# Stay below typical log-backend attribute caps after nested JSON is flattened.
_MAX_FLAT_PAYLOAD_ATTRIBUTES = 200
# Cap JSON size before base64 so the encoded field stays within common log value limits.
_MAX_BASE64_PAYLOAD_JSON_UTF8_BYTES = 120 * 1024

_SENSITIVE_HEADER_NAME_PATTERN = re.compile(
    r"(authorization|auth|signature|token|secret|cookie|api[-_]?key|password|credential)",
    re.IGNORECASE,
)


def count_flat_attributes(payload: dict[str, Any], *, limit: int | None = None) -> int:
    """Estimate how many leaf attributes nested JSON would flatten into.

    ``len(payload)`` and JSON byte size only measure how big the object is.
    Nested values become extra attributes, so we walk leaves.
    Pass ``limit`` to stop early; ``None`` counts the full payload.
    """

    def _count(node: Any) -> int:
        if isinstance(node, dict) and node:
            total = 0
            for item in node.values():
                total += _count(item)
                if limit is not None and total >= limit:
                    return limit
            return total
        if isinstance(node, list) and node:
            total = 0
            for item in node:
                total += _count(item)
                if limit is not None and total >= limit:
                    return limit
            return total
        return 1

    return _count(payload)


def _truncate_utf8_bytes(data: bytes, max_len: int) -> bytes:
    if len(data) <= max_len:
        return data
    truncated = data[:max_len]
    while truncated and (truncated[-1] & 0b11000000) == 0b10000000:
        truncated = truncated[:-1]
    return truncated


def build_added_to_queue_payload_log_fields(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Build payload fields for a single live-event log when full payload logging is on.

    Small payloads stay as nested JSON. Payloads that would flatten into too
    many log attributes are logged as a single base64 string so the event is
    not dropped by the log backend.
    """
    if (
        count_flat_attributes(payload, limit=_MAX_FLAT_PAYLOAD_ATTRIBUTES + 1)
        <= _MAX_FLAT_PAYLOAD_ATTRIBUTES
    ):
        return {"payload": payload}

    payload_bytes = json.dumps(payload, default=str, separators=(",", ":")).encode(
        "utf-8"
    )
    truncated = len(payload_bytes) > _MAX_BASE64_PAYLOAD_JSON_UTF8_BYTES
    encoded_bytes = _truncate_utf8_bytes(
        payload_bytes, _MAX_BASE64_PAYLOAD_JSON_UTF8_BYTES
    )
    fields: dict[str, Any] = {
        "payload_b64": base64.b64encode(encoded_bytes).decode("ascii"),
    }
    if truncated:
        fields["payload_b64_truncated"] = True
    return fields


def is_sensitive_header_name(header_name: str) -> bool:
    return bool(_SENSITIVE_HEADER_NAME_PATTERN.search(header_name))


def sanitize_headers_for_logging(headers: Mapping[str, str]) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        if is_sensitive_header_name(key):
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = value
    return sanitized


def _get_nested_value(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_nested_value(target: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = target
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[parts[-1]] = value


def pick_nested_fields(payload: dict[str, Any], paths: Iterable[str]) -> dict[str, Any]:
    """Copy selected dot-path fields from a payload (for integration log identifiers)."""
    identifiers: dict[str, Any] = {}
    for path in paths:
        value = _get_nested_value(payload, path)
        if value is not None and value != "":
            _set_nested_value(identifiers, path, value)
    return identifiers


def _is_generic_delivery_or_event_header(header_name: str) -> bool:
    lower = header_name.lower()
    if is_sensitive_header_name(header_name):
        return False
    if lower == "x-request-id":
        return True
    if not lower.startswith("x-"):
        return False
    if lower.endswith("-event") or lower.endswith("-delivery"):
        return True
    return "webhook-identifier" in lower or lower.endswith("-webhook-uuid")


def extract_compact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Include delivery/event style headers without integration-specific allowlists."""
    compact: dict[str, str] = {}
    for key, value in headers.items():
        if _is_generic_delivery_or_event_header(key):
            compact[key] = value
    return compact


_FINISH_TIMESTAMP_VALUES = frozenset(
    {
        "Finished Processing Successfully",
        "Finished Processing With Error",
    }
)


def build_live_event_timestamp_log_fields(
    timestamp_value: str,
    payload: dict[str, Any],
    headers: Mapping[str, str],
    *,
    trace_id: str,
    log_full_payload: bool,
    webhook_path: str | None = None,
    extra_identifiers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build structured fields for Event * timestamp log lines."""
    fields: dict[str, Any] = {"trace_id": trace_id}

    if timestamp_value in _FINISH_TIMESTAMP_VALUES:
        return fields

    if webhook_path is not None:
        fields["webhook_path"] = webhook_path

    if log_full_payload:
        fields["headers"] = sanitize_headers_for_logging(headers)
        fields.update(build_added_to_queue_payload_log_fields(payload))
        if extra_identifiers:
            fields["event_identifiers"] = extra_identifiers
        return fields

    compact_headers = extract_compact_headers(headers)
    if compact_headers:
        fields["headers"] = compact_headers

    if extra_identifiers:
        fields["payload"] = extra_identifiers

    return fields
