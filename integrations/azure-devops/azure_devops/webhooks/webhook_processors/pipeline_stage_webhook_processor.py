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


class PipelineStageWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.PIPELINE_STAGE]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        resource = payload["resource"]
        if "id" not in resource or "project" not in resource:
            return False
        project = resource["project"]
        if "id" not in project:
            return False
        return True

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            event_type = event.payload["eventType"]
            # Process stages when build completes (stages are available from build timeline)
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

        build_url = (
            f"{client._organization_base_url}/{project_id}/{API_URL_PREFIX}"
            f"/build/builds/{build_id}"
        )
        build_response = await client.send_request("GET", build_url)

        if not build_response:
            logger.warning(
                f"Build with ID {build_id} not found in project {project_id}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        build_data = build_response.json()

        # Fetch stages from build timeline
        stages = await client._fetch_stages_for_build(project, build_data)

        return WebhookEventRawResults(
            updated_raw_results=stages, deleted_raw_results=[]
        )
