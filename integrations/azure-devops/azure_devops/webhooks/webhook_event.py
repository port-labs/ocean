from typing import Optional
from pydantic import BaseModel


class WebhookEvent(BaseModel):
    id: Optional[str] = None
    publisherId: str
    eventType: str
    consumerId: str = "webHooks"
    consumerActionId: str = "httpRequest"
    consumerInputs: Optional[dict[str, str]] = None
    status: Optional[str] = None

    def set_consumer_url(self, url: str) -> None:
        self.consumerInputs = {"url": url}

    def get_event_by_subscription(
        self, subscribed_events: list["WebhookEvent"]
    ) -> "WebhookEvent" | None:
        for subscribed_event in subscribed_events:
            if (
                subscribed_event.publisherId == self.publisherId
                and subscribed_event.eventType == self.eventType
                and subscribed_event.consumerInputs == self.consumerInputs
            ):
                return subscribed_event

        return None

    def is_enabled(self) -> bool:
        return self.status == "enabled"
