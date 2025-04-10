from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from utils import PortGithubResources


class GithubIssueWebhookHandler(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        header = event.headers
        return header.get("X_GitHub_Event") == "issues"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [PortGithubResources.ISSUE]

    async def handle_event(
        self, event: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        match event.get("action"):
            case "created" | "closed":
                return WebhookEventRawResults(
                    updated_raw_results=[event["issue"]], deleted_raw_results=[]
                )
            case "deleted":
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[event["issue"]]
                )
            case _:
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True
