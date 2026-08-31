from datetime import datetime
from enum import Enum
from typing import Any


def serialize_probe_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: serialize_probe_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_probe_value(item) for item in value]
    return value
