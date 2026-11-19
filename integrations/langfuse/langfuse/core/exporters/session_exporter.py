import json
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from loguru import logger
from port_ocean.core.incremental.strategies import ServerSideTimestampStrategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from langfuse.clients.http.langfuse_client import PAGE_SIZE
from langfuse.core.exporters.abstract_exporter import AbstractLangfuseExporter
from langfuse.core.options import ListSessionOptions, SingleSessionOptions

SESSION_INCREMENTAL = ServerSideTimestampStrategy(param_key="fromStartTime")
DEFAULT_LOOKBACK_DAYS = 7
# Sessions are reconstructed from observations (legacy /sessions removed on Cloud v4).
_SESSION_ID_PRESENT = json.dumps(
    [
        {
            "type": "string",
            "column": "sessionId",
            "operator": "is not empty",
            "value": "",
        }
    ]
)


def _lookback_start(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


def _merge_session(sessions: dict[str, RAW_ITEM], obs: dict[str, Any]) -> None:
    session_id = obs.get("sessionId")
    if not session_id:
        return
    start = obs.get("startTime") or obs.get("createdAt")
    existing = sessions.get(session_id)
    if existing is None:
        sessions[session_id] = {
            "id": session_id,
            "createdAt": start,
            "updatedAt": start,
            "environment": obs.get("environment"),
            "userId": obs.get("userId"),
            "projectId": obs.get("projectId"),
        }
        return
    if start and (not existing.get("createdAt") or start < existing["createdAt"]):
        existing["createdAt"] = start
    if start and (not existing.get("updatedAt") or start > existing["updatedAt"]):
        existing["updatedAt"] = start


class SessionExporter(AbstractLangfuseExporter):
    async def get_resource(self, options: SingleSessionOptions) -> Optional[RAW_ITEM]:
        lookback = options.get("lookback_days") or DEFAULT_LOOKBACK_DAYS
        params: dict[str, Any] = {
            "fields": "basic,time",
            "sessionId": options["session_id"],
            "fromStartTime": _lookback_start(lookback),
        }
        sessions: dict[str, RAW_ITEM] = {}
        async for batch in self.client.send_cursor_paginated_request(
            "v2/observations", params=params
        ):
            for obs in batch:
                _merge_session(sessions, obs)

        session = sessions.get(options["session_id"])
        if not session:
            logger.warning(f"Langfuse session not found: {options['session_id']}")
            return None
        return session

    async def get_paginated_resources(
        self, options: ListSessionOptions | None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        lookback = (options or {}).get("lookback_days") or DEFAULT_LOOKBACK_DAYS
        from_start = (options or {}).get("from_start_time") or _lookback_start(lookback)
        params: dict[str, Any] = {
            "fields": "basic,time",
            "fromStartTime": from_start,
            "filter": _SESSION_ID_PRESENT,
        }

        # ponytail: accumulate then batch — fine for lookback window; shard if memory bites
        sessions: dict[str, RAW_ITEM] = {}
        async for batch in self.client.send_cursor_paginated_request(
            "v2/observations", params=params
        ):
            for obs in batch:
                _merge_session(sessions, obs)

        items = list(sessions.values())
        for i in range(0, len(items), PAGE_SIZE):
            yield items[i : i + PAGE_SIZE]
