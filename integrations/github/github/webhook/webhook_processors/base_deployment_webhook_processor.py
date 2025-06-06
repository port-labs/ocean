from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
)

from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)


class BaseDeploymentWebhookProcessor(BaseRepositoryWebhookProcessor):

    async def _validate_payload(self, payload: EventPayload) -> bool:
        return bool(
            payload.get("deployment", {}).get("id")
            and payload.get("deployment", {}).get("environment")
        )

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") in [
            "deployment",
            "deployment_status",
        ]
