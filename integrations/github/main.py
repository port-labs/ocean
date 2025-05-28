from typing import cast
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from github.clients.client_factory import create_github_client
from github.clients.utils import integration_config
from github.helpers.utils import ObjectKind
from github.webhook.events import WEBHOOK_CREATE_EVENTS
from github.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from github.webhook.webhook_processors.dependabot_alert_webhook_processor import (
    DependabotAlertWebhookProcessor,
)
from github.webhook.webhook_processors.code_scanning_alert_webhook_processor import (
    CodeScanningAlertWebhookProcessor,
)
from github.webhook.webhook_client import GithubWebhookClient
from github.core.exporters.repository_exporter import RestRepositoryExporter
from github.core.exporters.dependabot_alert_exporter import RestDependabotAlertExporter
from github.core.exporters.code_scanning_alert_exporter import (
    RestCodeScanningAlertExporter,
)
from github.core.options import (
    ListRepositoryOptions,
    ListDependabotAlertOptions,
    ListCodeScanningAlertOptions,
    ListReleaseOptions,
    ListTagOptions,
    ListBranchOptions,
)
from port_ocean.context.event import event
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from integration import (
    GithubPortAppConfig,
    GithubDependabotAlertConfig,
    GithubCodeScanningAlertConfig,
)
from github.core.exporters.release_exporter import RestReleaseExporter
from github.core.exporters.tag_exporter import RestTagExporter
from github.core.exporters.branch_exporter import RestBranchExporter
from github.webhook.webhook_processors.release_webhook_processor import ReleaseWebhookProcessor
from github.webhook.webhook_processors.tag_webhook_processor import TagWebhookProcessor
from github.webhook.webhook_processors.branch_webhook_processor import BranchWebhookProcessor


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
        **integration_config(),
        webhook_secret=ocean.integration_config["webhook_secret"],
    )

    logger.info("Subscribing to GitHub webhooks")
    await client.upsert_webhook(base_url, WEBHOOK_CREATE_EVENTS)


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all repositories in the organization."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    exporter = RestRepositoryExporter(rest_client)

    port_app_config = cast("GithubPortAppConfig", event.port_app_config)
    options = ListRepositoryOptions(type=port_app_config.repository_type)

    async for repositories in exporter.get_paginated_resources(options):
        yield repositories


@ocean.on_resync(ObjectKind.DEPENDABOT_ALERT)
async def resync_dependabot_alerts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all Dependabot alerts in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    repository_exporter = RestRepositoryExporter(rest_client)
    dependabot_alert_exporter = RestDependabotAlertExporter(rest_client)

    config = cast(GithubDependabotAlertConfig, event.resource_config)
    async for repositories in repository_exporter.get_paginated_resources():
        tasks = [
            dependabot_alert_exporter.get_paginated_resources(
                ListDependabotAlertOptions(
                    repo_name=repo["name"],
                    state=config.selector.state,
                )
            )
            for repo in repositories
        ]
        async for alerts in stream_async_iterators_tasks(*tasks):
            yield alerts


@ocean.on_resync(ObjectKind.CODE_SCANNING_ALERT)
async def resync_code_scanning_alerts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all code scanning alerts in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    repository_exporter = RestRepositoryExporter(rest_client)
    code_scanning_alert_exporter = RestCodeScanningAlertExporter(rest_client)

    config = cast(GithubCodeScanningAlertConfig, event.resource_config)
    async for repositories in repository_exporter.get_paginated_resources():
        tasks = [
            code_scanning_alert_exporter.get_paginated_resources(
                ListCodeScanningAlertOptions(
                    repo_name=repo["name"],
                    state=config.selector.state,
                )
            )
            for repo in repositories
        ]
        async for alerts in stream_async_iterators_tasks(*tasks):
            yield alerts


@ocean.on_resync(ObjectKind.RELEASE)
async def resync_releases(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all releases in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    repository_exporter = RestRepositoryExporter(rest_client)
    release_exporter = RestReleaseExporter(rest_client)
    
    async for repositories in repository_exporter.get_paginated_resources():
        tasks = [
            release_exporter.get_paginated_resources(
                ListReleaseOptions(repo_name=repo["name"])
            )
            for repo in repositories
        ]
        async for releases in stream_async_iterators_tasks(*tasks):
            yield releases


@ocean.on_resync(ObjectKind.TAG)
async def resync_tags(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all tags in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    repository_exporter = RestRepositoryExporter(rest_client)
    tag_exporter = RestTagExporter(rest_client)
    
    async for repositories in repository_exporter.get_paginated_resources():
        tasks = [
            tag_exporter.get_paginated_resources(
                ListTagOptions(repo_name=repo["name"])
            )
            for repo in repositories
        ]
        async for tags in stream_async_iterators_tasks(*tasks):
            yield tags


@ocean.on_resync(ObjectKind.BRANCH)
async def resync_branches(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all branches in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    repository_exporter = RestRepositoryExporter(rest_client)
    branch_exporter = RestBranchExporter(rest_client)
    
    async for repositories in repository_exporter.get_paginated_resources():
        tasks = [
            branch_exporter.get_paginated_resources(
                ListBranchOptions(repo_name=repo["name"])
            )
            for repo in repositories
        ]
        async for branches in stream_async_iterators_tasks(*tasks):
            yield branches


ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/webhook", DependabotAlertWebhookProcessor)
ocean.add_webhook_processor("/webhook", CodeScanningAlertWebhookProcessor)
ocean.add_webhook_processor("/webhook", ReleaseWebhookProcessor)
ocean.add_webhook_processor("/webhook", TagWebhookProcessor)
ocean.add_webhook_processor("/webhook", BranchWebhookProcessor)
