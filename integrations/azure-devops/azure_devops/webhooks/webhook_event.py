from typing import Optional
from pydantic.v1 import BaseModel

FULL_PAYLOAD_EVENT_TYPES = {"git.push"}
FULL_PAYLOAD_CONSUMER_INPUTS = {
    "resourceDetailsToSend": "all",
    "messagesToSend": "all",
    "detailedMessagesToSend": "all",
}


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
            **(FULL_PAYLOAD_CONSUMER_INPUTS if self.requires_full_payload() else {}),
            **(
                {
                    "basicAuthUsername": auth_username,
                    "basicAuthPassword": webhook_secret,
                }
                if webhook_secret and auth_username
                else {}
            ),
        }
        self.publisherInputs = {"projectId": project_id} if project_id else None

    def requires_full_payload(self) -> bool:
        return self.eventType in FULL_PAYLOAD_EVENT_TYPES

    def has_required_payload_details(self) -> bool:
        if not self.requires_full_payload():
            return True

        if not self.consumerInputs:
            return False

        return all(
            self.consumerInputs.get(key) == value
            for key, value in FULL_PAYLOAD_CONSUMER_INPUTS.items()
        )

    def get_event_by_subscription(
        self, subscribed_events: list["WebhookSubscription"]
    ) -> Optional["WebhookSubscription"]:
        if not self.consumerInputs:
            return None

        current_url = self.consumerInputs.get("url")
        current_project_id = (self.publisherInputs or {}).get("projectId")

        for subscribed_event in subscribed_events:
            if not subscribed_event.consumerInputs:
                continue

            subscribed_url = subscribed_event.consumerInputs.get("url")
            subscribed_project_id = (subscribed_event.publisherInputs or {}).get(
                "projectId"
            )

            if (
                subscribed_event.publisherId == self.publisherId
                and subscribed_event.eventType == self.eventType
                and subscribed_url == current_url
                and subscribed_project_id == current_project_id
            ):
                return subscribed_event

        return None

    def is_enabled(self) -> bool:
        return self.status == "enabled"
