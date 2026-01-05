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
from azure_devops.webhooks.events import PipelineEvents


class PipelineRunWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.PIPELINE_RUN]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        resource = payload["resource"]
        if (
            "id" not in resource
            or "definition" not in resource
            or "project" not in resource
        ):
            return False
        definition = resource["definition"]
        if "id" not in definition:
            return False
        project = resource["project"]
        if "id" not in project:
            return False
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            event_type = event.payload["eventType"]
            return event_type == PipelineEvents.BUILD_COMPLETED
        except (KeyError, ValueError):
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = AzureDevopsClient.create_from_ocean_config()
        resource = payload["resource"]

        from azure_devops.client.azure_devops_client import API_URL_PREFIX

        build_id = resource["id"]
        project = resource["project"]
        project_id = project["id"]
        definition = resource["definition"]
        pipeline_id = definition["id"]

        # Fetch the pipeline run using the Pipelines API
        # In Azure DevOps, a build IS a pipeline run
        run_url = (
            f"{client._organization_base_url}/{project_id}/{API_URL_PREFIX}"
            f"/pipelines/{pipeline_id}/runs/{build_id}"
        )
        run_response = await client.send_request("GET", run_url)

        if not run_response:
            logger.warning(
                f"Pipeline run with ID {build_id} not found for pipeline {pipeline_id} in project {project_id}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        run_data = run_response.json()
        run_data["__project"] = project
        run_data["__pipeline"] = {"id": str(pipeline_id), "__projectId": project_id}

        return WebhookEventRawResults(
            updated_raw_results=[run_data], deleted_raw_results=[]
        )
