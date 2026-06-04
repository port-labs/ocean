from typing import Any

from pydantic import BaseModel, Field, validator
from port_ocean.core.handlers.webhook.webhook_event import EventPayload, WebhookEvent

from datadog.client import DatadogClient
from datadog.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
)
from initialize_client import init_client


class AuditTrailAsset(BaseModel):
    type: str = ""
    id: str | None = None

    @validator("type", pre=True, always=True)
    @classmethod
    def normalize_type(cls, v: object) -> str:
        return str(v).lower() if v is not None else ""


class AuditTrailEvt(BaseModel):
    name: str = ""

    @validator("name", pre=True, always=True)
    @classmethod
    def normalize_name(cls, v: object) -> str:
        return str(v).strip() if v is not None else ""


class AuditTrailUsr(BaseModel):
    uuid: str | None = None
    id: str | None = None


class AuditTrailAttributes(BaseModel):
    evt: AuditTrailEvt = Field(default_factory=AuditTrailEvt)
    action: str = ""
    asset: AuditTrailAsset | None = None
    usr: AuditTrailUsr | None = None

    @validator("action", pre=True, always=True)
    @classmethod
    def normalize_action(cls, v: object) -> str:
        return str(v).lower() if v is not None else ""


class AuditTrailEvent(BaseModel):
    attributes: AuditTrailAttributes = Field(default_factory=AuditTrailAttributes)


class BaseAuditTrailProcessor(BaseWebhookProcessor):
    """Base for all audit-trail webhook processors.

    Each WebhookEvent carries exactly one event dict — batches are split
    upstream by DatadogLiveEventsProcessorManager.
    """

    def __init__(self, event: WebhookEvent) -> None:
        super().__init__(event)
        self.client: DatadogClient = init_client()

    @staticmethod
    def parse_event(payload: dict[str, Any]) -> AuditTrailEvent:
        return AuditTrailEvent.parse_obj(payload)

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not isinstance(payload, dict):
            return False
        event = self.parse_event(payload)
        return event.attributes.asset is not None and event.attributes.asset.id is not None
