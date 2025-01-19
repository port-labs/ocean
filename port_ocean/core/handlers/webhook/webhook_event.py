import datetime
from enum import StrEnum
from typing import Any, Dict, TypeAlias
from uuid import uuid4
from fastapi import Request


# Use TypeAlias instead of 'type' for Python <3.12 compatibility
EventPayload: TypeAlias = Dict[str, Any]


class WebhookEventTimestamp(StrEnum):
    """Enum for timestamp keys."""

    AddedToQueue = "AddedToQueue"
    StartedProcessing = "StartedProcessing"


class WebhookEvent:
    """Represents a webhook event."""

    def __init__(
        self,
        trace_id: str,
        payload: EventPayload,
        headers: Dict[str, str],
        original_request: Request,
        timestamps: Dict[str, datetime.datetime] | None = None,
    ) -> None:
        self.trace_id = trace_id
        self.payload = payload
        self.headers = headers
        self._timestamps = timestamps or {}
        self._original_request = original_request

    @staticmethod
    async def from_request(request: Request) -> "WebhookEvent":
        trace_id = str(uuid4())
        payload = await request.json()

        return WebhookEvent(
            trace_id=trace_id,
            payload=payload,
            headers=dict(request.headers),
            original_request=request,
        )

    def set_timestamp(self, timestamp: WebhookEventTimestamp) -> None:
        if self._timestamps.get(timestamp.value):
            raise ValueError(f"Timestamp {timestamp.value} already set")

        self._timestamps[timestamp.value] = datetime.datetime.now()

    def get_timestamp(
        self, timestamp: WebhookEventTimestamp
    ) -> datetime.datetime | None:
        return self._timestamps.get(timestamp.value, None)
