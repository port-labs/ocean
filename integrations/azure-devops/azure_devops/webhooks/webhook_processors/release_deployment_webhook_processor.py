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
from azure_devops.webhooks.events import ReleaseDeploymentEvents
from azure_devops.client.azure_devops_client import (
    AzureDevopsClient,
    RELEASE_PUBLISHER_ID,
)


class ReleaseDeploymentWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.RELEASE_DEPLOYMENT]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        project_id = payload.get("resourceContainers", {}).get("project", {}).get("id")
        if not project_id:
            return False

        resource = payload.get("resource", {})
        deployment = resource.get("deployment")
        if deployment:
            release_id = deployment.get("release", {}).get("id")
            environment_id = deployment.get("definitionEnvironmentId")
            return release_id is not None and environment_id is not None

        environment = resource.get("environment", {})
        if environment.get("releaseId") and environment.get("definitionEnvironmentId"):
            return True

        return False

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            if event.payload["publisherId"] != RELEASE_PUBLISHER_ID:
                return False
            event_type = event.payload["eventType"]
            return bool(ReleaseDeploymentEvents(event_type))
        except (KeyError, ValueError):
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = AzureDevopsClient.create_from_ocean_config()
        project_id = payload["resourceContainers"]["project"]["id"]
        resource = payload["resource"]

        if "deployment" in resource:
            release_id = resource["deployment"]["release"]["id"]
            environment_id = resource["deployment"]["definitionEnvironmentId"]
        else:
            release_id = resource["environment"]["releaseId"]
            environment_id = resource["environment"]["definitionEnvironmentId"]

        deployment = await client.get_release_deployment(
            project_id, release_id, environment_id
        )
        if not deployment:
            logger.warning(
                f"Release deployment not found for release {release_id} "
                f"environment {environment_id} in project {project_id}, skipping event..."
            )
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        return WebhookEventRawResults(
            updated_raw_results=[deployment],
            deleted_raw_results=[],
        )
