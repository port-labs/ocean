from abc import ABC
from enum import StrEnum
from typing import Any, Dict, Type, TypeAlias, Optional
from uuid import uuid4
from fastapi import Request
from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import RAW_ITEM


EventPayload: TypeAlias = Dict[str, Any]
EventHeaders: TypeAlias = Dict[str, str]


class LiveEventTimestamp(StrEnum):
    """Enum for timestamp keys"""

    AddedToQueue = "Added To Queue"
    StartedProcessing = "Started Processing"
    FinishedProcessingSuccessfully = "Finished Processing Successfully"
    FinishedProcessingWithError = "Finished Processing With Error"


class LiveEvent(ABC):
    """Represents a live event marker class"""

    def set_timestamp(
        self, timestamp: LiveEventTimestamp, params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Set a timestamp for a specific event

        Args:
            timestamp: The timestamp type to set
            params: Additional parameters to log with the event
        """
        log_params = params or {}
        logger.info(
            f"Event {timestamp.value}",
            extra=log_params | {"timestamp_type": timestamp.value},
        )
        self._timestamp = timestamp


class WebhookEvent(LiveEvent):
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

    def set_timestamp(
        self, timestamp: LiveEventTimestamp, params: Optional[Dict[str, Any]] = None
    ) -> None:
        """Set a timestamp for a specific event"""
        super().set_timestamp(
            timestamp,
            params={
                "trace_id": self.trace_id,
                "payload": self.payload,
                "headers": self.headers,
            },
        )


class WebhookEventRawResults:
    """
    Class for webhook event to store the updated data for the event
    """

    def __init__(
        self,
        updated_raw_results: list[RAW_ITEM],
        deleted_raw_results: list[RAW_ITEM],
    ) -> None:
        self._resource: ResourceConfig | None = None
        self._updated_raw_results = updated_raw_results
        self._deleted_raw_results = deleted_raw_results

    @property
    def resource(self) -> ResourceConfig:
        if self._resource is None:
            raise ValueError("Resource has not been set")
        return self._resource

    @resource.setter
    def resource(self, value: ResourceConfig) -> None:
        self._resource = value

    @property
    def updated_raw_results(self) -> list[RAW_ITEM]:
        return self._updated_raw_results

    @property
    def deleted_raw_results(self) -> list[RAW_ITEM]:
        return self._deleted_raw_results
