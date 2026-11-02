import json
from typing import Any

from loguru import logger


def parse_cloud_control_properties(raw: Any) -> dict[str, Any]:
    """Deserialize Cloud Control ``Properties`` JSON into a dict.

    ListResources / GetResource return Properties as a JSON string. Invalid or
    missing payloads yield an empty dict so a single bad resource cannot fail
    the batch.
    """
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(
            "Failed to parse Cloud Control Properties JSON, skipping payload"
        )
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed
