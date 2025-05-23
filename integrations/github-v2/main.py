from typing import cast
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from github.core.exporters.exporter_factory import ExporterFactory
from github.clients.client_factory import create_github_client
from github.helpers.utils import GithubClientType, ObjectKind
from github.webhook.events import WEBHOOK_CREATE_EVENTS
from github.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from github.webhook.webhook_processors.deployment_webhook_processor import (
    DeploymentWebhookProcessor,
)
from github.webhook.webhook_client import GithubWebhookClient
from github.core.options import ListDeploymentsOptions, ListEnvironmentsOptions
from port_ocean.utils.async_iterators import stream_async_iterators_tasks



@ocean.on_start()
async def on_start() -> None:
    """Initialize the integration and set up webhooks."""
    logger.info("Starting Port Ocean GitHub integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    base_url = ocean.app.base_url
    if not base_url:
        return

    client: GithubWebhookClient = cast(
        GithubWebhookClient,
        create_github_client(
            GithubClientType.WEBHOOK,
            webhook_secret=ocean.integration_config["webhook_secret"],
        ),
    )

    logger.info("Subscribing to GitHub webhooks")
    await client.upsert_webhook(base_url, WEBHOOK_CREATE_EVENTS)


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all repositories in the organization."""
    logger.info(f"Starting resync for kind: {kind}")

    client = create_github_client()
    exporter_factory = ExporterFactory()
    exporter = exporter_factory.get_exporter(ObjectKind(kind))(client)

    async for repositories in exporter.get_paginated_resources():
        yield repositories


@ocean.on_resync(ObjectKind.DEPLOYMENT)
async def resync_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all deployments in the organization."""
    logger.info(f"Starting resync for kind: {kind}")
    
    rest_client = create_github_client()
    exporter_factory = ExporterFactory()

    repository_exporter = exporter_factory.get_exporter(ObjectKind.REPOSITORY)(rest_client)
    deployment_exporter = exporter_factory.get_exporter(ObjectKind.DEPLOYMENT)(rest_client)


    async for repositories in repository_exporter.get_paginated_resources():
        tasks = [
            deployment_exporter.get_paginated_resources(
                ListDeploymentsOptions(
                    repo_name=repo["name"],
                )
            )
            for repo in repositories
        ]
        async for deployments in stream_async_iterators_tasks(*tasks):
            yield deployments

 

@ocean.on_resync(ObjectKind.ENVIRONMENT)
async def resync_environments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all environments in the organization."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    exporter_factory = ExporterFactory()
    repository_exporter = exporter_factory.get_exporter(ObjectKind.REPOSITORY)(rest_client)
    environment_exporter = exporter_factory.get_exporter(ObjectKind.ENVIRONMENT)(rest_client)

    async for repositories in repository_exporter.get_paginated_resources():
        tasks = [
            environment_exporter.get_paginated_resources(
                ListEnvironmentsOptions(
                    repo_name=repo["name"],
                )
            )
            for repo in repositories
        ]
        async for environments in stream_async_iterators_tasks(*tasks):
            print("environments", environments)
            yield environments



ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/webhook", DeploymentWebhookProcessor)
