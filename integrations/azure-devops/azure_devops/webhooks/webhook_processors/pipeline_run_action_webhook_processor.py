from loguru import logger

from azure_devops.actions.utils import build_external_id
from azure_devops.client.azure_devops_client import PIPELINES_PUBLISHER_ID
from azure_devops.webhooks.events import PipelineRunEvents
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    WebhookProcessorType,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

PIPELINE_RUN_COMPLETED_STATE = "completed"
PIPELINE_RUN_SUCCEEDED_RESULT = "succeeded"


class PipelineRunActionWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    """Report ``trigger_pipeline`` action completion from run-state-changed events.

    Unlike the catalog pipeline-run processor, this is an ACTION processor: it
    correlates the completed pipeline run back to its Port action run via the
    external id set at trigger time and reports the final success/failure.
    """

    @classmethod
    def get_processor_type(cls) -> WebhookProcessorType:
        return WebhookProcessorType.ACTION

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return []

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            if event.payload["publisherId"] != PIPELINES_PUBLISHER_ID:
                return False
            return bool(PipelineRunEvents(event.payload["eventType"]))
        except (KeyError, ValueError):
            return False

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False
        project_id = payload.get("resourceContainers", {}).get("project", {}).get("id")
        run = payload.get("resource", {}).get("run", {})
        pipeline_id = payload.get("resource", {}).get("pipeline", {}).get("id")
        return bool(project_id and run.get("id") and pipeline_id)

    async def _handle_webhook_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        empty_results = WebhookEventRawResults(
            updated_raw_results=[], deleted_raw_results=[]
        )
        run_resource = payload["resource"]["run"]
        if run_resource.get("state") != PIPELINE_RUN_COMPLETED_STATE:
            logger.debug(
                f"Ignoring pipeline run event in state '{run_resource.get('state')}'",
                run_id=run_resource.get("id"),
                state=run_resource.get("state"),
            )
            return empty_results

        project_id = payload["resourceContainers"]["project"]["id"]
        pipeline_id = payload["resource"]["pipeline"]["id"]
        run_id = run_resource["id"]
        external_id = build_external_id(str(project_id), str(pipeline_id), str(run_id))

        port_run = await ocean.port_client.find_run_by_external_id(external_id)
        if not port_run:
            # Expected for pipeline runs not triggered via the trigger_pipeline
            # action (e.g. manual runs, other triggers), so this stays at debug.
            logger.debug(
                f"No Port action run found for completed pipeline run {run_id}",
                external_id=external_id,
                project_id=project_id,
                pipeline_id=pipeline_id,
            )
            return empty_results
        if not ocean.port_client.is_run_in_progress(port_run):
            logger.debug(
                f"Port run {port_run.id} is no longer in progress, skipping completion report",
                run_id=port_run.id,
                external_id=external_id,
            )
            return empty_results
        if not port_run.execution_properties.get("reportPipelineStatus", True):
            logger.info(
                f"reportPipelineStatus is disabled for Port run {port_run.id}, skipping completion report",
                run_id=port_run.id,
                external_id=external_id,
            )
            return empty_results

        result = run_resource.get("result")
        is_success = result == PIPELINE_RUN_SUCCEEDED_RESULT
        logger.info(
            f"Reporting pipeline run completion for Port run {port_run.id}",
            run_id=port_run.id,
            result=result,
        )
        await ocean.port_client.report_run_completed(
            port_run, is_success, f"Pipeline run {result}"
        )
        return empty_results
