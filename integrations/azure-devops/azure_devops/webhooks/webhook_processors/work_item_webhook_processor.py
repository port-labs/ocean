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

        resource = payload.get("resource", {})
        work_item_id = resource.get("id")
        return work_item_id is not None

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            event_type = event.payload["eventType"]
            return bool(WorkItemEvents(event_type))
        except ValueError:
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = AzureDevopsClient.create_from_ocean_config()
        resource = payload["resource"]
        work_item_id = resource.get("id")
        project_id = resource.get("project", {}).get("id")

        if not work_item_id:
            logger.warning("Work item webhook payload missing work item ID")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if not project_id:
            logger.warning("Work item webhook payload missing project ID")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        event_type = payload.get("eventType", "")

        # Handle work item deletion
        if event_type == WorkItemEvents.WORK_ITEM_DELETED:
            logger.info(f"Work item {work_item_id} deleted, returning for deletion")
            # Return a minimal work item structure for deletion
            deleted_work_item = {
                "id": work_item_id,
                "__projectId": project_id,
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

            return WebhookEventRawResults(
                updated_raw_results=[work_item], deleted_raw_results=[]
            )
        except Exception as e:
            logger.error(f"Error processing work item webhook event: {e}")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )
