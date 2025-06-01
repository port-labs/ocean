from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)


class MergeRequestWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["merge_request"]
    hooks = ["Merge Request Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.MERGE_REQUEST]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        merge_request_id = payload["object_attributes"]["id"]
        project_id = payload["project"]["id"]
        logger.info(
            f"Handling merge request webhook event for project {project_id} and merge request {merge_request_id}"
        )

        merge_request = await self._gitlab_webhook_client.get_merge_request(
            project_id, merge_request_id
        )

        return WebhookEventRawResults(
            updated_raw_results=[merge_request],
            deleted_raw_results=[],
        )
