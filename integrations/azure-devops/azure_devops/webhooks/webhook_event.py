from typing import Any, Optional
from pydantic import BaseModel


class WebhookEvent(BaseModel):
    publisherId: str
    eventType: str
    consumerId: str = "webHooks"
    consumerActionId: str = "httpRequest"
    consumerInputs: Optional[dict[str, str]] = None

    def set_consumer_url(self, url: str) -> None:
        self.consumerInputs = {"url": url}

    def __hash__(self) -> int:
        return hash((self.publisherId, self.eventType, str(self.consumerInputs)))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, WebhookEvent):
            return False
        return (
            other.publisherId == self.publisherId
            and other.eventType == self.eventType
            and other.consumerInputs == self.consumerInputs
        )
