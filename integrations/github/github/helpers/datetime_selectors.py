from __future__ import annotations

import re
from datetime import datetime, timezone

from port_ocean.utils.time import convert_str_to_utc_datetime

ISO_8601_DATE_REGEX = r"^\d{4}-\d{2}-\d{2}$"
ISO_8601_SELECTOR_REGEX = (
    r"^("
    r"\d{4}-\d{2}-\d{2}"
    r"|"
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})$"
    r")$"
)


def parse_selector_iso_datetime(value: str) -> datetime:
    """Parse an ISO 8601 date or datetime selector value as UTC."""
    stripped = value.strip()
    if re.fullmatch(ISO_8601_DATE_REGEX, stripped):
        return datetime.fromisoformat(f"{stripped}T00:00:00+00:00").astimezone(
            timezone.utc
        )
    return convert_str_to_utc_datetime(stripped)
