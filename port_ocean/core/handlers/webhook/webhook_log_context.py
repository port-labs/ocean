import base64
import json
from typing import Any

# Stay below typical log-backend attribute caps after nested JSON is flattened.
_MAX_FLAT_PAYLOAD_ATTRIBUTES = 200
# Cap JSON size before base64 so the encoded field stays within common log value limits.
_MAX_BASE64_PAYLOAD_JSON_UTF8_BYTES = 120 * 1024


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
    """Build payload fields for a single Event Added To Queue log.

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
