from typing import cast

from loguru import logger
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from azure_devops.misc import Kind
from azure_devops.webhooks.events import PullRequestEvents
from integration import AzureDevopsPullRequestResourceConfig


class PullRequestWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.PULL_REQUEST]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        return payload["resource"].get("pullRequestId") is not None

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            event_type = event.payload["eventType"]
            return bool(PullRequestEvents(event_type))
        except ValueError:
            return False

    async def _handle_webhook_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = self._get_client_for_webhook(payload)
        pull_request_id = payload["resource"]["pullRequestId"]
        pull_request_data = await client.get_pull_request(pull_request_id)

        if not pull_request_data:
            logger.warning(f"Pull request with ID {pull_request_id} not found")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        selector = cast(AzureDevopsPullRequestResourceConfig, resource_config).selector
        if selector.enrich_with_commits or selector.enrich_with_review_discussion:
            enriched = await client.enrich_pull_requests(
                [pull_request_data],
                enrich_with_commits=selector.enrich_with_commits,
                enrich_with_review_discussion=selector.enrich_with_review_discussion,
                concurrency=1,
            )
            pull_request_data = enriched[0] if enriched else pull_request_data

        return WebhookEventRawResults(
            updated_raw_results=[pull_request_data], deleted_raw_results=[]
        )
