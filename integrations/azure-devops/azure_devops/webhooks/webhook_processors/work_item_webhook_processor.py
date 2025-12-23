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
from azure_devops.webhooks.events import WorkItemEvents


class WorkItemWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.WORK_ITEM]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        resource = payload["resource"]
        work_item_id = resource.get("id")
        if work_item_id is None:
            return False

        try:
            project_id = payload["resourceContainers"]["project"]["id"]
            return project_id is not None
        except (KeyError, TypeError):
            return False

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            event_type = event.payload["eventType"]
            return bool(WorkItemEvents(event_type))
        except (KeyError, ValueError):
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = AzureDevopsClient.create_from_ocean_config()
        resource = payload["resource"]
        work_item_id = resource["id"]
        project_id = payload["resourceContainers"]["project"]["id"]

        event_type = payload["eventType"]

        project = await client.get_single_project(project_id)
        if not project:
            logger.warning(
                f"Project with ID {project_id} not found, cannot enrich work item"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        # Handle work item deletion
        if event_type == WorkItemEvents.WORK_ITEM_DELETED:
            logger.info(f"Work item {work_item_id} deleted, returning for deletion")
            deleted_work_item = {
                "id": work_item_id,
            }
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[deleted_work_item]
            )

        # For created, updated, and commented events, fetch the full work item
        try:
            work_item = await client.get_work_item(project_id, work_item_id)

            if not work_item:
                logger.warning(
                    f"Work item with ID {work_item_id} not found in project {project_id}"
                )
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

            # Add project context to work item
            work_item["__projectId"] = project_id
            work_item["__project"] = project

            return WebhookEventRawResults(
                updated_raw_results=[work_item], deleted_raw_results=[]
            )
        except Exception as e:
            logger.error(f"Error processing work item webhook event: {e}")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )
