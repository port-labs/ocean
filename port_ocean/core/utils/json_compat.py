from datetime import date, datetime
from typing import Any


def make_json_compatible(value: Any) -> Any:
    """
    Convert common non-JSON-native Python objects into JSON-compatible types.

    Intended for normalizing inputs before passing them to jq (pyjq),
    which expects JSON-serializable values.
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): make_json_compatible(v) for k, v in value.items()}
    if isinstance(value, list):
        return [make_json_compatible(v) for v in value]
    return value
