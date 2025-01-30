from enum import StrEnum
from typing import Any, Dict, Type, TypeAlias
from uuid import uuid4
from fastapi import Request
from loguru import logger


EventPayload: TypeAlias = Dict[str, Any]
EventHeaders: TypeAlias = Dict[str, str]


class WebhookEventTimestamp(StrEnum):
    """Enum for timestamp keys"""

    AddedToQueue = "Added To Queue"
    StartedProcessing = "Started Processing"
    FinishedProcessingSuccessfully = "Finished Processing Successfully"
    FinishedProcessingWithError = "Finished Processing With Error"


class WebhookEvent:
    """Represents a webhook event"""

    def __init__(
        self,
        trace_id: str,
        payload: EventPayload,
        headers: EventHeaders,
        original_request: Request | None = None,
    ) -> None:
        self.trace_id = trace_id
        self.payload = payload
        self.headers = headers
        self._original_request = original_request

    @classmethod
    async def from_request(
        cls: Type["WebhookEvent"], request: Request
    ) -> "WebhookEvent":
        trace_id = str(uuid4())
        payload = await request.json()

        return cls(
            trace_id=trace_id,
            payload=payload,
            headers=dict(request.headers),
            original_request=request,
        )

    @classmethod
    def from_dict(cls: Type["WebhookEvent"], data: Dict[str, Any]) -> "WebhookEvent":
        return cls(
            trace_id=data["trace_id"],
            payload=data["payload"],
            headers=data["headers"],
            original_request=None,
        )

    def clone(self) -> "WebhookEvent":
        return WebhookEvent(
            trace_id=self.trace_id,
            payload=self.payload,
            headers=self.headers,
            original_request=self._original_request,
        )

    def set_timestamp(self, timestamp: WebhookEventTimestamp) -> None:
        """Set a timestamp for a specific event"""
        logger.info(
            f"Webhook Event {timestamp.value}",
            extra={
                "trace_id": self.trace_id,
                "payload": self.payload,
                "headers": self.headers,
                "timestamp_type": timestamp.value,
            },
        )
