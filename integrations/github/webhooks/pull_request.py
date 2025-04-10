from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEventRawResults,
    WebhookEvent,
)

from utils import PortGithubResources


class GithubPRWebhookHandler(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        header = event.headers
        return header.get("X_GitHub_Event") == "pull_request"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [PortGithubResources.PR]

    async def handle_event(
        self, event: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        match event.get("action"):
            case "opened" | "closed":
                return WebhookEventRawResults(
                    updated_raw_results=[event["pull_request"]], deleted_raw_results=[]
                )
            case _:
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True
