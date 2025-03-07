from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from bitbucket_integration.webhook.events import PullRequestEvents
from bitbucket_integration.utils import ObjectKind
from bitbucket_integration.webhook.processors._base import _BaseWebhookProcessorConfig


class PullRequestWebhookProcessor(_BaseWebhookProcessorConfig):

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            return bool(PullRequestEvents(event.headers["x-event-key"]))
        except ValueError:
            return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PULL_REQUEST]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        logger.warning(f"Received pull request webhook event: {payload}")
        pull_request_id = payload["pullrequest"]["id"]
        repository_id = payload["repository"]["uuid"]
        pull_request_details = await self._webhook_client.get_pull_request(
            repository_id, pull_request_id
        )
        return WebhookEventRawResults(
            updated_raw_results=[pull_request_details],
            deleted_raw_results=[],
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        required_fields = ["repository", "pullrequest"]
        return all(field in payload for field in required_fields)
