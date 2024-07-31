from typing import Optional
from pydantic import BaseModel


class WebhookEvent(BaseModel):
    id: Optional[str] = None
    publisherId: str
    eventType: str
    consumerId: str = "webHooks"
    consumerActionId: str = "httpRequest"
    consumerInputs: Optional[dict[str, str]] = None
    publisherInputs: Optional[dict[str, str]] = None
    status: Optional[str] = None

    def set_webhook_details(self, url: str, project_id: Optional[str] = None) -> None:
        self.consumerInputs = {"url": url}
        if project_id:
            self.publisherInputs = {"projectId": project_id}

    def get_event_by_subscription(
        self, subscribed_events: list["WebhookEvent"]
    ) -> Optional["WebhookEvent"]:
        for subscribed_event in subscribed_events:
            if (
                subscribed_event.publisherId == self.publisherId
                and subscribed_event.eventType == self.eventType
                and subscribed_event.consumerInputs == self.consumerInputs
            ):
                if not self.publisherInputs and not subscribed_event.publisherInputs:
                    return subscribed_event

                # Azure Devops sends more than just the projectId in the publisherInputs,
                # And we only need to verify the projectId
                if self.publisherInputs and subscribed_event.publisherInputs:
                    if subscribed_event.publisherInputs.get(
                        "projectId", None
                    ) == self.publisherInputs.get("projectId", None):
                        return subscribed_event

        return None

    def is_enabled(self) -> bool:
        return self.status == "enabled"
