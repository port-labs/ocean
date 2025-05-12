import json
from typing import Any


def json_safe(obj: Any) -> Any:
    """Recursively convert (de)serialisable objects so `json.dumps` does not crash."""
    return json.loads(json.dumps(obj, default=str))
