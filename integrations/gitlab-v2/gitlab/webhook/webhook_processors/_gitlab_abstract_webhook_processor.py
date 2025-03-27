from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)
from gitlab.clients.client_factory import create_gitlab_client


class _GitlabAbstractWebhookProcessor(AbstractWebhookProcessor):
    events: list[str]
    hook: str

    _gitlab_webhook_client = create_gitlab_client()

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_name = str(
            event.payload.get("event_name") or event.payload.get("event_type")
        )
        return bool(
            self.hook == event.headers["x-gitlab-event"] and event_name in self.events
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        return not ({"object_kind", "project"} - payload.keys())
