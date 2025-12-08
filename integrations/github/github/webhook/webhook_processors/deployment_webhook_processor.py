from loguru import logger
from github.helpers.utils import ObjectKind
from github.clients.client_factory import create_github_client

from github.core.options import SingleDeploymentOptions
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from github.core.exporters.deployment_exporter import RestDeploymentExporter
from github.webhook.webhook_processors.base_deployment_webhook_processor import (
    BaseDeploymentWebhookProcessor,
)
from integration import GithubDeploymentConfig, GithubDeploymentSelector
from typing import cast, Any


class DeploymentWebhookProcessor(BaseDeploymentWebhookProcessor):

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.DEPLOYMENT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        deployment = payload["deployment"]
        deployment_id = str(deployment["id"])
        repo = payload["repository"]["name"]
        resource_config_kind = resource_config.kind
        organization = payload["organization"]["login"]

        logger.info(
            f"Processing deployment event: {action} for {resource_config_kind} in {repo} from {organization}"
        )

        config = cast(GithubDeploymentConfig, resource_config)

        if not self._check_deployment_filters(config.selector, deployment):
            logger.info(
                f"Deployment {repo}/{deployment_id} filtered out by selector criteria"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        client = create_github_client()
        deployment_exporter = RestDeploymentExporter(client)
        data_to_upsert = await deployment_exporter.get_resource(
            SingleDeploymentOptions(
                organization=organization,
                repo_name=repo,
                id=deployment_id,
            )
        )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )

    def _check_deployment_filters(
        self, selector: GithubDeploymentSelector, deployment: dict[str, Any]
    ) -> bool:
        """Check if deployment matches selector task and environment filters."""

        # Check task filter
        if selector.task and deployment["task"] != selector.task:
            return False

        # Check environment filter
        if selector.environment and deployment["environment"] != selector.environment:
            return False

        return True
