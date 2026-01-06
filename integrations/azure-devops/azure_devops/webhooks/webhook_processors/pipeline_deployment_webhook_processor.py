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


class PipelineDeploymentWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.PIPELINE_DEPLOYMENT]

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
            return event_type == PipelineEvents.BUILD_COMPLETED
        except (KeyError, ValueError):
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Handle build complete event and fetch any associated pipeline deployments.

        Note: Azure DevOps doesn't have a direct webhook event for pipeline deployments.
        This processor fetches deployments that may be associated with the completed build.
        """
        client = AzureDevopsClient.create_from_ocean_config()
        resource = payload["resource"]

        from azure_devops.client.azure_devops_client import API_URL_PREFIX

        build_id = resource["id"]
        project = resource["project"]
        project_id = project["id"]

        # Fetch environments for the project
        environments_url = (
            f"{client._organization_base_url}/{project_id}/{API_URL_PREFIX}"
            f"/distributedtask/environments"
        )

        environments_response = await client.send_request("GET", environments_url)
        if not environments_response:
            logger.debug(f"No environments found for project {project_id}")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        environments_data = environments_response.json()
        environments = environments_data.get("value", [])

        # Fetch deployments for each environment
        all_deployments = []
        for environment in environments:
            environment_id = environment["id"]
            deployments_url = (
                f"{client._organization_base_url}/{project_id}/{API_URL_PREFIX}"
                f"/distributedtask/environments/{environment_id}/environmentdeploymentrecords"
            )

            deployments_response = await client.send_request("GET", deployments_url)
            if not deployments_response:
                continue

            deployments_data = deployments_response.json()
            deployments = deployments_data.get("value", [])

            # Filter deployments related to this build
            for deployment in deployments:
                # Check if deployment is related to this build
                if deployment.get("definition", {}).get("id") == build_id:
                    deployment["__project"] = project
                    all_deployments.append(deployment)

        if all_deployments:
            logger.info(
                f"Found {len(all_deployments)} pipeline deployments for build {build_id}"
            )

        return WebhookEventRawResults(
            updated_raw_results=all_deployments, deleted_raw_results=[]
        )
