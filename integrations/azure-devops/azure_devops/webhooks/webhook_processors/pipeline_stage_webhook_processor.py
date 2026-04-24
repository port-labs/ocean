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
from azure_devops.webhooks.events import PipelineStageEvents
from azure_devops.client.azure_devops_client import (
    AzureDevopsClient,
    PIPELINES_PUBLISHER_ID,
)


class PipelineStageWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.PIPELINE_STAGE]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        project_id = payload.get("resourceContainers", {}).get("project", {}).get("id")
        run_id = payload.get("resource", {}).get("run", {}).get("id")
        stage_id = payload.get("resource", {}).get("stage", {}).get("id")
        pipeline_id = payload.get("resource", {}).get("pipeline", {}).get("id")
        return (
            project_id is not None
            and run_id is not None
            and stage_id is not None
            and pipeline_id is not None
        )

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            if event.payload["publisherId"] != PIPELINES_PUBLISHER_ID:
                return False
            event_type = event.payload["eventType"]
            return bool(PipelineStageEvents(event_type))
        except (KeyError, ValueError):
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = AzureDevopsClient.create_from_ocean_config()
        pipeline_id = payload["resource"]["pipeline"]["id"]
        project_id = payload["resourceContainers"]["project"]["id"]
        run_id = payload["resource"]["run"]["id"]
        stage_id = payload["resource"]["stage"]["id"]

        project = await client.get_single_project(project_id)
        if not project:
            logger.warning(
                f"Project with ID {project_id} not found for pipeline run {run_id}, skipping event..."
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        pipeline_stage = await client.get_pipeline_stage(
            project, pipeline_id, run_id, stage_id
        )
        if not pipeline_stage:
            logger.warning(
                f"Pipeline stage with ID {stage_id} not found, skipping event..."
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        return WebhookEventRawResults(
            updated_raw_results=[pipeline_stage],
            deleted_raw_results=[],
        )
