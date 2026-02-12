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
from azure_devops.webhooks.events import PipelineEvents
from azure_devops.client.azure_devops_client import (
    AzureDevopsClient,
    PIPELINES_PUBLISHER_ID,
)
from integration import AzureDevopsPipelineResourceConfig


class PipelineWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.PIPELINE]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        project_id = payload.get("resourceContainers", {}).get("project", {}).get("id")
        return project_id is not None and "checkConfigurationId" in payload["resource"]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            if event.payload["publisherId"] != PIPELINES_PUBLISHER_ID:
                return False
            event_type = event.payload["eventType"]
            return bool(PipelineEvents(event_type))
        except (KeyError, ValueError):
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = AzureDevopsClient.create_from_ocean_config()
        pipeline_id = payload["resource"]["checkConfigurationId"]
        project_id = payload["resourceContainers"]["project"]["id"]

        pipeline = await client.get_pipeline(project_id, pipeline_id)
        if not pipeline:
            logger.warning(
                f"Pipeline with ID {pipeline_id} not found, skipping event..."
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        selector = cast(AzureDevopsPipelineResourceConfig, resource_config).selector
        if selector.include_repo:
            logger.info(f"Enriching pipeline: {pipeline_id} with repository")
            pipelines = await client.enrich_pipelines_with_repository([pipeline])
            return WebhookEventRawResults(
                updated_raw_results=pipelines,
                deleted_raw_results=[],
            )

        return WebhookEventRawResults(
            updated_raw_results=[pipeline],
            deleted_raw_results=[],
        )
