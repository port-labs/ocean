from datetime import date, datetime
import re
from typing import Any


class JQInputNotJsonSerializableError(TypeError):
    """Raised when jq input_value receives non-JSON-native Python types."""


_NOT_JSON_SERIALIZABLE_RE = re.compile(r"not\s+JSON\s+serializable", re.IGNORECASE)


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


def compile_jq(compiled_pattern: Any, data: Any) -> Any:
    """
    Call `compiled_pattern.input_value(data)` and raise a typed exception when jq
    cannot serialize the input (e.g. due to date/datetime).
    """
    try:
        return compiled_pattern.input_value(data)
    except TypeError as exc:
        if _NOT_JSON_SERIALIZABLE_RE.search(str(exc)):
            raise JQInputNotJsonSerializableError(str(exc)) from exc
        raise
