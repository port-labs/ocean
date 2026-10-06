from github.webhook.events import PULL_REQUEST_REVIEW_EVENTS
from github.webhook.webhook_processors.base_pull_request_webhook_processor import (
    BasePullRequestWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
)


class PullRequestReviewWebhookProcessor(BasePullRequestWebhookProcessor):
    async def _validate_payload(self, payload: EventPayload) -> bool:
        return await super()._validate_payload(payload) and "review" in payload

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.headers.get("x-github-event") == "pull_request_review"
            and event.payload.get("action") in PULL_REQUEST_REVIEW_EVENTS
        )
