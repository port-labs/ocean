from typing import Any, cast, TYPE_CHECKING

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from github.clients.client_factory import (
    GitHubAuthenticatorFactory,
    create_github_client,
)
from github.clients.utils import integration_config
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.exporters.issue_exporter import RestIssueExporter
from github.core.exporters.pull_request_exporter import RestPullRequestExporter
from github.core.exporters.repository_exporter import RestRepositoryExporter
from github.core.options import (
    ListIssueOptions,
    ListPullRequestOptions,
    ListRepositoryOptions,
)
from github.helpers.utils import ObjectKind, GithubClientType
from github.webhook.events import WEBHOOK_CREATE_EVENTS
from github.webhook.webhook_client import GithubWebhookClient
from github.webhook.webhook_processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)
from github.webhook.webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from github.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from github.core.exporters.rest_team_exporter import RestTeamExporter
from github.core.exporters.graphql_team_exporter import GraphQLTeamExporter
from github.core.exporters.user_exporter import GraphQLUserExporter

from github.webhook.webhook_processors.team_webhook_processor import (
    TeamWebhookProcessor,
)
from github.webhook.webhook_processors.user_webhook_processor import (
    UserWebhookProcessor,
)
from integration import GithubTeamConfig

if TYPE_CHECKING:
    from integration import (
        GithubIssueConfig,
        GithubPortAppConfig,
        GithubPullRequestConfig,
    )


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

    authenticator = GitHubAuthenticatorFactory.create(
        organization=ocean.integration_config["github_organization"],
        github_host=ocean.integration_config["github_host"],
        token=ocean.integration_config.get("github_token"),
        app_id=ocean.integration_config.get("github_app_id"),
        private_key=ocean.integration_config.get("github_app_private_key"),
    )

    client = GithubWebhookClient(
        **integration_config(authenticator),
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


@ocean.on_resync(ObjectKind.USER)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all users in the organization."""
    logger.info(f"Starting resync for kind: {kind}")

    graphql_client = create_github_client(GithubClientType.GRAPHQL)
    exporter = GraphQLUserExporter(graphql_client)

    async for users in exporter.get_paginated_resources():
        yield users


@ocean.on_resync(ObjectKind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all teams in the organization."""
    logger.info(f"Starting resync for kind: {kind}")

    config = cast(GithubTeamConfig, event.resource_config)
    selector = config.selector

    exporter: AbstractGithubExporter[Any]
    if selector.include_members:
        graphql_client = create_github_client(GithubClientType.GRAPHQL)
        exporter = GraphQLTeamExporter(graphql_client)
    else:
        rest_client = create_github_client(GithubClientType.REST)
        exporter = RestTeamExporter(rest_client)

    async for teams in exporter.get_paginated_resources(None):
        yield teams


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all pull requests in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    repository_exporter = RestRepositoryExporter(rest_client)
    pull_request_exporter = RestPullRequestExporter(rest_client)
    config = cast("GithubPullRequestConfig", event.resource_config)

    repo_options = ListRepositoryOptions(
        type=cast("GithubPortAppConfig", event.port_app_config).repository_type
    )

    async for repos in repository_exporter.get_paginated_resources(
        options=repo_options
    ):
        tasks = [
            pull_request_exporter.get_paginated_resources(
                ListPullRequestOptions(
                    repo_name=repo["name"],
                    state=config.selector.state,
                )
            )
            for repo in repos
        ]
        async for pull_requests in stream_async_iterators_tasks(*tasks):
            yield pull_requests


@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all issues from repositories."""
    logger.info(f"Starting resync for kind {kind}")

    rest_client = create_github_client()
    repository_exporter = RestRepositoryExporter(rest_client)
    issue_exporter = RestIssueExporter(rest_client)
    config = cast("GithubIssueConfig", event.resource_config)

    repo_options = ListRepositoryOptions(
        type=cast("GithubPortAppConfig", event.port_app_config).repository_type
    )

    async for repos in repository_exporter.get_paginated_resources(
        options=repo_options
    ):
        tasks = [
            issue_exporter.get_paginated_resources(
                ListIssueOptions(
                    repo_name=repo["name"],
                    state=config.selector.state,
                )
            )
            for repo in repos
        ]
        async for issues in stream_async_iterators_tasks(*tasks):
            yield issues


ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/webhook", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
ocean.add_webhook_processor("/webhook", UserWebhookProcessor)
ocean.add_webhook_processor("/webhook", TeamWebhookProcessor)
