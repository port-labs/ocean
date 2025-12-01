from typing import cast
from loguru import logger
from github.helpers.utils import ObjectKind
from github.clients.client_factory import create_github_client

from github.core.options import SingleEnvironmentOptions
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from github.core.exporters.environment_exporter import RestEnvironmentExporter
from github.webhook.webhook_processors.base_deployment_webhook_processor import (
    BaseDeploymentWebhookProcessor,
)
from integration import GithubRepoSearchConfig


class EnvironmentWebhookProcessor(BaseDeploymentWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ENVIRONMENT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        environment = payload["deployment"]["environment"]
        repo = payload["repository"]["name"]
        resource_config_kind = resource_config.kind
        organization = payload["organization"]["login"]

        logger.info(
            f"Processing deployment event: {action} for {resource_config_kind} in {repo} from {organization}"
        )
        config = cast(GithubRepoSearchConfig, resource_config)

        if config.selector.repo_search is not None:
            logger.info(
                "search query is configured for this kind, checking if repository is in matched results."
            )
            if await self.repo_in_search(payload, resource_config) is None:
                logger.info(
                    "Repository is not matched by search query, no actions will be performed."
                )
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

        client = create_github_client()
        environment_exporter = RestEnvironmentExporter(client)
        data_to_upsert = await environment_exporter.get_resource(
            SingleEnvironmentOptions(
                organization=organization,
                repo_name=repo,
                name=environment,
            )
        )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
