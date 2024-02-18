from typing import Optional
from pydantic import BaseModel


class WebhookEvent(BaseModel):
    publisherId: str
    eventType: str
    consumerId: str = "webHooks"
    consumerActionId: str = "httpRequest"
    consumerInputs: Optional[dict[str, str]] = None

    def set_consumer_url(self, url: str) -> None:
        self.consumerInputs = {"url": url}

    def is_event_subscribed(self, subscribed_events) -> bool:  # type: ignore
        for subscribed_event in subscribed_events:
            if (
                subscribed_event.publisherId == self.publisherId
                and subscribed_event.eventType == self.eventType
                and subscribed_event.consumerInputs == self.consumerInputs
            ):
                return True
        return False
