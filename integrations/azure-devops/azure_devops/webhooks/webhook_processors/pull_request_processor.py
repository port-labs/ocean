from loguru import logger
from azure_devops.client.azure_devops_client import AzureDevopsClient
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


class PullRequestWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    EVENT_TYPES = [
        "git.pullrequest.updated",
        "git.pullrequest.created",
    ]

    def __init__(self, event: WebhookEvent):
        super().__init__(event)

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not await super().should_process_event(event):
            return False

        event_type = event.payload.get("eventType")
        return event_type in self.EVENT_TYPES

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.PULL_REQUEST]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = AzureDevopsClient.create_from_ocean_config()
        pull_request_id = payload["resource"]["pullRequestId"]
        pull_request_data = await client.get_pull_request(pull_request_id)

        if not pull_request_data:
            logger.warning(f"Pull request with ID {pull_request_id} not found")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        return WebhookEventRawResults(
            updated_raw_results=[pull_request_data], deleted_raw_results=[]
        )
