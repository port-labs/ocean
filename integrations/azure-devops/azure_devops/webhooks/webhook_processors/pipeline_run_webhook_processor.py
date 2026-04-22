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
from azure_devops.webhooks.events import PipelineRunEvents
from azure_devops.client.azure_devops_client import (
    AzureDevopsClient,
    PIPELINES_PUBLISHER_ID,
)
from integration import AzureDevopsTestRunResourceConfig


class PipelineRunWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.PIPELINE_RUN, Kind.TEST_RUN]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        project_id = payload.get("resourceContainers", {}).get("project", {}).get("id")
        run_id = payload.get("resource", {}).get("run", {}).get("id")
        pipeline_id = payload.get("resource", {}).get("pipeline", {}).get("id")
        return project_id is not None and run_id is not None and pipeline_id is not None

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            if event.payload["publisherId"] != PIPELINES_PUBLISHER_ID:
                return False
            event_type = event.payload["eventType"]
            return bool(PipelineRunEvents(event_type))
        except (KeyError, ValueError):
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = AzureDevopsClient.create_from_ocean_config()
        pipeline_id = payload["resource"]["pipeline"]["id"]
        project_id = payload["resourceContainers"]["project"]["id"]
        run_id = payload["resource"]["run"]["id"]

        if resource_config.kind == Kind.TEST_RUN:
            return await self._handle_test_run(
                client, project_id, str(run_id), resource_config
            )

        pipeline_run = await client.get_pipeline_run(project_id, pipeline_id, run_id)
        if not pipeline_run:
            logger.warning(
                f"Pipeline run with ID {run_id} not found, skipping event..."
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )
        project = await client.get_single_project(project_id)
        if not project:
            logger.warning(
                f"Project with ID {project_id} not found for pipeline run {run_id}, skipping event..."
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )
        pipeline = await client.get_pipeline(project_id, pipeline_id)
        if not pipeline:
            logger.warning(
                f"Pipeline with ID {pipeline_id} not found for pipeline run {run_id}, skipping event..."
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )
        # enrich pipeline run with project and pipeline data
        client.annotate_runs([pipeline_run], project=project, pipeline=pipeline)

        return WebhookEventRawResults(
            updated_raw_results=[pipeline_run],
            deleted_raw_results=[],
        )

    async def _handle_test_run(
        self,
        client: AzureDevopsClient,
        project_id: str,
        build_id: str,
        resource_config: ResourceConfig,
    ) -> WebhookEventRawResults:
        config = cast(AzureDevopsTestRunResourceConfig, resource_config)
        test_runs = await client.get_test_runs_by_build(
            project_id,
            build_id,
            config.selector.include_results,
            config.selector.code_coverage,
        )
        if not test_runs:
            logger.info(
                f"No test runs found for build {build_id} in project {project_id}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        logger.info(
            f"Found {len(test_runs)} test runs for build {build_id} in project {project_id}"
        )
        return WebhookEventRawResults(
            updated_raw_results=test_runs,
            deleted_raw_results=[],
        )
