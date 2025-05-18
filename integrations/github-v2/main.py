import typing
from loguru import logger
from integration import GithubPullRequestConfig, GithubRepositoryConfig
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


from github.clients.client_factory import create_github_client
from github.utils import ObjectKind
from github.webhook.events import WEBHOOK_CREATE_EVENTS
from github.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from github.webhook.webhook_client import GithubWebhookClient
from github.core.exporters.repository_exporter import RepositoryExporter
from github.core.options import ListRepositoryOptions
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from github.core.exporters.pull_request_exporter import PullRequestExporter
from github.webhook.webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from github.core.options import ListPullRequestOptions


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

    client = GithubWebhookClient(
        token=ocean.integration_config["github_token"],
        organization=ocean.integration_config["github_organization"],
        github_host=ocean.integration_config["github_host"],
        webhook_secret=ocean.integration_config["webhook_secret"],
    )

    logger.info("Subscribing to GitHub webhooks")
    await client.upsert_webhook(base_url, WEBHOOK_CREATE_EVENTS)


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all repositories in the organization."""
    logger.info(f"Starting resync for kind: {kind}")

    client = create_github_client()
    exporter = RepositoryExporter(client)

    config = typing.cast(GithubRepositoryConfig, event.resource_config)
    options = ListRepositoryOptions(type=config.selector.type)

    async for repositories in exporter.get_paginated_resources(options=options):
        yield repositories


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all pull requests in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    client = create_github_client()

    repository_exporter = RepositoryExporter(client)
    pull_request_exporter = PullRequestExporter(client)

    config = typing.cast(GithubPullRequestConfig, event.resource_config)
    repo_options = ListRepositoryOptions(type="all")

    async for repos in repository_exporter.get_paginated_resources(
        options=repo_options
    ):
        tasks = [
            pull_request_exporter.get_paginated_resources(
                ListPullRequestOptions(
                    state=config.selector.state,
                    repo_name=repo["name"],
                )
            )
            for repo in repos
        ]
        async for pull_requests in stream_async_iterators_tasks(*tasks):
            yield pull_requests


ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/webhook", PullRequestWebhookProcessor)
