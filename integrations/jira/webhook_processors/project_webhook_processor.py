from loguru import logger
from initialize_client import create_jira_client
from kinds import Kinds
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


class ProjectWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.payload.get("webhookEvent", "").startswith("project_")

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.PROJECT]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        webhook_event = payload.get("webhookEvent", "")

        client = create_jira_client()
        project_key = payload["project"]["key"]

        if webhook_event == "project_soft_deleted":
            logger.info(f"Project {project_key} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[payload["project"]],
            )

        logger.debug(f"Fetching project with key: {project_key}")
        item = await client.get_single_project(project_key)

        if not item:
            logger.warning(f"Failed to retrieve {Kinds.PROJECT}")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        data_to_update = []
        data_to_delete = []
        logger.debug(f"Retrieved {Kinds.PROJECT} item: {item}")

        if "deleted" in webhook_event:
            data_to_delete.extend([item])
        else:
            data_to_update.extend([item])

        return WebhookEventRawResults(
            updated_raw_results=data_to_update,
            deleted_raw_results=data_to_delete,
        )
