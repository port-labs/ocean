from github.webhook.events import PULL_REQUEST_EVENTS
from github.webhook.webhook_processors.base_pull_request_webhook_processor import (
    BasePullRequestWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent


class PullRequestWebhookProcessor(BasePullRequestWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.headers.get("x-github-event") == "pull_request"
            and event.payload.get("action") in PULL_REQUEST_EVENTS
        )
