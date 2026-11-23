import time
from typing import Any

from core.tracking.tags import MANAGED_TAG

SECONDS_PER_DAY = 24 * 60 * 60


def build_sessions_query(
    *,
    include_archived: bool,
    created_after_days: int | None,
    origins: list[str] | None,
    only_managed_by_port: bool,
    now: float | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if not include_archived:
        params["is_archived"] = False
    if created_after_days is not None:
        current = time.time() if now is None else now
        params["created_after"] = int(current - created_after_days * SECONDS_PER_DAY)
    if origins:
        params["origins"] = list(origins)
    if only_managed_by_port:
        params["tags"] = [MANAGED_TAG]
    return params