from typing import cast

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from integration import (
    GitlabDeploymentResourceConfig,
)
from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)


class DeploymentWebhookProcessor(_GitlabAbstractWebhookProcessor):
    """Processes GitLab Deployment Hook events for both deployment."""

    events = ["deployment"]
    hooks = ["Deployment Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.DEPLOYMENT]

    async def handle_event(
        self,
        payload: EventPayload,
        resource_config: ResourceConfig,
    ) -> WebhookEventRawResults:
        deployment_id: int = payload["deployment_id"]
        project_id: int = payload["project"]["id"]

        selector = cast(
            GitlabDeploymentResourceConfig,
            resource_config,
        ).selector

        full_project = await self._gitlab_webhook_client.get_project(str(project_id))

        if not full_project:
            logger.warning(
                f"Project with ID {project_id} not found for deployment {deployment_id}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if selector.include_only_active_projects and full_project.get("archived"):
            logger.info(
                f"Skipping deployment {deployment_id} in archived project {full_project['path_with_namespace']} due to selector settings."
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if selector.query_params:
            if (
                selector.query_params.environment
                and payload.get("environment") != selector.query_params.environment
            ):
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )
            if (
                selector.query_params.status
                and payload.get("status") != selector.query_params.status
            ):
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

        logger.info(
            f"Handling deployment webhook event for deployment {deployment_id} "
            f"in project {full_project['path_with_namespace']} "
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

        if selector.query_params:
            updated_at = deployment.get("updated_at", "")
            if (
                selector.query_params.updated_after
                and updated_at < selector.query_params.updated_after
            ):
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )
            if (
                selector.query_params.updated_before
                and updated_at > selector.query_params.updated_before
            ):
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

            finished_at = (deployment.get("deployable") or {}).get("finished_at", "")
            if finished_at:
                if (
                    selector.query_params.finished_after
                    and finished_at < selector.query_params.finished_after
                ):
                    return WebhookEventRawResults(
                        updated_raw_results=[], deleted_raw_results=[]
                    )
                if (
                    selector.query_params.finished_before
                    and finished_at > selector.query_params.finished_before
                ):
                    return WebhookEventRawResults(
                        updated_raw_results=[], deleted_raw_results=[]
                    )

        deployment["__project"] = full_project

        return WebhookEventRawResults(
            updated_raw_results=[deployment],
            deleted_raw_results=[],
        )
