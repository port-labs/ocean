from loguru import logger
from github.helpers.utils import ObjectKind
from github.clients.client_factory import create_github_client

from github.core.options import SingleDeploymentStatusOptions
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from github.core.exporters.deployment_status_exporter import (
    RestDeploymentStatusExporter,
)
from github.webhook.webhook_processors.base_deployment_webhook_processor import (
    BaseDeploymentWebhookProcessor,
)
from integration import GithubDeploymentStatusConfig, GithubDeploymentStatusSelector
from typing import cast, Any


class DeploymentStatusWebhookProcessor(BaseDeploymentWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.DEPLOYMENT_STATUS]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "deployment_status"

    async def _validate_payload(self, payload: EventPayload) -> bool:
        return bool(
            payload.get("deployment_status", {}).get("id")
            and payload.get("deployment", {}).get("id")
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        deployment = payload["deployment"]
        deployment_status = payload["deployment_status"]
        repository = payload["repository"]
        deployment_id = str(deployment["id"])
        status_id = str(deployment_status["id"])
        repo = repository["name"]
        organization = self.get_webhook_payload_organization(payload)["login"]
        config = cast(GithubDeploymentStatusConfig, resource_config)

        logger.info(
            f"Processing deployment status event: for {resource_config.kind} in {repo} from {organization}"
        )
        if not self._check_deployment_filters(config.selector, deployment):
            logger.info(
                f"Deployment status {repo}/{status_id} filtered out by selector criteria"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if not await self.should_process_repo_search(payload, resource_config):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        client = create_github_client()
        deployment_status_exporter = RestDeploymentStatusExporter(client)
        data_to_upsert = await deployment_status_exporter.get_resource(
            SingleDeploymentStatusOptions(
                organization=organization,
                repo_name=repo,
                deployment_id=deployment_id,
                status_id=status_id,
            )
        )
        if not data_to_upsert:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )

    def _check_deployment_filters(
        self, selector: GithubDeploymentStatusSelector, deployment: dict[str, Any]
    ) -> bool:
        """Check if deployment matches selector task and environment filters."""

        deployment_task = deployment["task"]
        deployment_environment = deployment["environment"]

        if selector.task and deployment_task != selector.task:
            logger.debug(
                f"Deployment filtered: task mismatch "
                f"(selector={selector.task}, deployment={deployment_task})"
            )
            return False

        if selector.environment and deployment_environment != selector.environment:
            logger.debug(
                f"Deployment filtered: environment mismatch "
                f"(selector={selector.environment}, deployment={deployment_environment})"
            )
            return False

        return True
