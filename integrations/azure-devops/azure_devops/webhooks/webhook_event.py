from typing import Optional
from pydantic import BaseModel


class WebhookSubscription(BaseModel):
    id: Optional[str] = None
    publisherId: str
    eventType: str
    consumerId: str = "webHooks"
    consumerActionId: str = "httpRequest"
    consumerInputs: Optional[dict[str, str]] = None
    publisherInputs: Optional[dict[str, str]] = None
    status: Optional[str] = None

    def set_webhook_details(
        self,
        url: str,
        auth_username: str | None = None,
        webhook_secret: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> None:
        self.consumerInputs = {
            "url": url,
            **(
                {
                    "basicAuthUsername": auth_username,
                    "basicAuthPassword": webhook_secret,
                }
                if webhook_secret and auth_username
                else {}
            ),
        }
        if project_id:
            self.publisherInputs = {"projectId": project_id}

    def get_event_by_subscription(
        self, subscribed_events: list["WebhookSubscription"]
    ) -> Optional["WebhookSubscription"]:
        if not self.consumerInputs:
            return None

        current_url = self.consumerInputs.get("url")

        for subscribed_event in subscribed_events:
            if not subscribed_event.consumerInputs:
                continue

            subscribed_url = subscribed_event.consumerInputs.get("url")

            if (
                subscribed_event.publisherId == self.publisherId
                and subscribed_event.eventType == self.eventType
                and subscribed_url == current_url
            ):
                if not self.publisherInputs and not subscribed_event.publisherInputs:
                    return subscribed_event

                if self.publisherInputs and subscribed_event.publisherInputs:
                    if subscribed_event.publisherInputs.get(
                        "projectId"
                    ) == self.publisherInputs.get("projectId"):
                        return subscribed_event

        return None

    def is_enabled(self) -> bool:
        return self.status == "enabled"
