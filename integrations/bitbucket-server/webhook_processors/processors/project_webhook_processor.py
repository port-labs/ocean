from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from integration import ObjectKind
from webhook_processors.processors._bitbucket_abstract_webhook_processor import (
    BaseWebhookProcessorMixin,
)
from webhook_processors.webhook_client import PROJECT_WEBHOOK_EVENTS


class ProjectWebhookProcessor(BaseWebhookProcessorMixin):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload["eventKey"] in PROJECT_WEBHOOK_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PROJECT]

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        project_key = payload["new"]["key"]
        logger.info(f"Handling project webhook event for project: {project_key}")

        project_details = await self._client.get_single_project(project_key)

        return WebhookEventRawResults(
            updated_raw_results=[project_details],
            deleted_raw_results=[],
        )
