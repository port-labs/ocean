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


class PipelineWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["pipeline"]
    hooks = ["Pipeline Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PIPELINE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        pipeline_id = payload["object_attributes"]["id"]
        project_id = payload["project"]["id"]
        logger.info(
            f"Handling pipeline webhook event for project {project_id} and pipeline {pipeline_id}"
        )

        pipeline = await self._gitlab_webhook_client.get_pipeline(
            project_id, pipeline_id
        )

        return WebhookEventRawResults(
            updated_raw_results=[pipeline],
            deleted_raw_results=[],
        )
