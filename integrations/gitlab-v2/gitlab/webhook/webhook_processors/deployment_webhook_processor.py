from typing import Any

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)


class DeploymentWebhookProcessor(_GitlabAbstractWebhookProcessor):
    """Processes GitLab Deployment Hook events for both deployment and deployment-status kinds."""

    events = ["deployment"]
    hooks = ["Deployment Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.DEPLOYMENT, ObjectKind.DEPLOYMENT_STATUS]

    async def handle_event(
        self,
        payload: EventPayload,
        resource_config: ResourceConfig,
    ) -> WebhookEventRawResults:
        deployment_id: int = payload["deployment_id"]
        project: dict[str, Any] = payload["project"]
        project_id: int = project["id"]

        logger.info(
            f"Handling deployment webhook event for deployment {deployment_id} "
            f"in project {project['path_with_namespace']} "
            f"(status={payload.get('status')})"
        )

        deployment = await self._gitlab_webhook_client.get_single_deployment(
            project_id=project_id,
            deployment_id=deployment_id,
        )

        if not deployment:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        deployment["__project"] = project

        return WebhookEventRawResults(
            updated_raw_results=[deployment],
            deleted_raw_results=[],
        )
