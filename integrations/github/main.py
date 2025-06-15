from typing import cast

from loguru import logger
from github.core.exporters.workflows_exporter import RestWorkflowExporter
from github.webhook.registry import register_live_events_webhooks
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from github.clients.client_factory import (
    GitHubAuthenticatorFactory,
    create_github_client,
)
from github.core.exporters.workflow_runs_exporter import RestWorkflowRunExporter
from github.clients.utils import integration_config
from github.core.exporters.branch_exporter import RestBranchExporter
from github.core.exporters.deployment_exporter import RestDeploymentExporter
from github.core.exporters.environment_exporter import RestEnvironmentExporter
from github.core.exporters.issue_exporter import RestIssueExporter
from github.core.exporters.pull_request_exporter import RestPullRequestExporter
from github.core.exporters.repository_exporter import RestRepositoryExporter
from github.core.exporters.release_exporter import RestReleaseExporter
from github.core.exporters.tag_exporter import RestTagExporter
from github.core.exporters.dependabot_exporter import RestDependabotAlertExporter
from github.core.exporters.code_scanning_alert_exporter import (
    RestCodeScanningAlertExporter,
)

from github.core.options import (
    ListBranchOptions,
    ListDeploymentsOptions,
    ListEnvironmentsOptions,
    ListIssueOptions,
    ListPullRequestOptions,
    ListRepositoryOptions,
    ListWorkflowOptions,
    ListWorkflowRunOptions,
    ListReleaseOptions,
    ListTagOptions,
    ListDependabotAlertOptions,
    ListCodeScanningAlertOptions,
)
from github.helpers.utils import ObjectKind
from github.webhook.events import WEBHOOK_CREATE_EVENTS
from github.webhook.webhook_client import GithubWebhookClient

from integration import (
    GithubIssueConfig,
    GithubPortAppConfig,
    GithubPullRequestConfig,
    GithubDependabotAlertConfig,
    GithubCodeScanningAlertConfig,
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

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    options = ListRepositoryOptions(type=port_app_config.repository_type)

    async for repositories in exporter.get_paginated_resources(options):
        yield repositories


@ocean.on_resync(ObjectKind.WORKFLOW)
async def resync_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all workflows for specified Github repositories"""
    logger.info(f"Starting resync for kind: {kind}")
    client = create_github_client()
    repo_exporter = RestRepositoryExporter(client)
    workflow_exporter = RestWorkflowExporter(client)

    port_app_config = cast("GithubPortAppConfig", event.port_app_config)
    options = ListRepositoryOptions(type=port_app_config.repository_type)

    async for repositories in repo_exporter.get_paginated_resources(options=options):
        tasks = (
            workflow_exporter.get_paginated_resources(
                options=ListWorkflowOptions(repo_name=repo["name"])
            )
            for repo in repositories
        )
        async for workflows in stream_async_iterators_tasks(*tasks):
            yield workflows


@ocean.on_resync(ObjectKind.WORKFLOW_RUN)
async def resync_workflow_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all workflow runs for specified Github repositories"""
    logger.info(f"Starting resync for kind: {kind}")

    client = create_github_client()
    repo_exporter = RestRepositoryExporter(client)
    workflow_run_exporter = RestWorkflowRunExporter(client)
    workflow_exporter = RestWorkflowExporter(client)

    port_app_config = cast("GithubPortAppConfig", event.port_app_config)
    options = ListRepositoryOptions(type=port_app_config.repository_type)

    async for repositories in repo_exporter.get_paginated_resources(options=options):
        for repo in repositories:
            workflow_options = ListWorkflowOptions(repo_name=repo["name"])
            async for workflows in workflow_exporter.get_paginated_resources(
                options=workflow_options
            ):
                tasks = (
                    workflow_run_exporter.get_paginated_resources(
                        options=ListWorkflowRunOptions(
                            repo_name=repo["name"],
                            workflow_id=workflow["id"],
                            max_runs=100,
                        )
                    )
                    for workflow in workflows
                )
                async for runs in stream_async_iterators_tasks(*tasks):
                    yield runs


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all pull requests in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    repository_exporter = RestRepositoryExporter(rest_client)
    pull_request_exporter = RestPullRequestExporter(rest_client)
    config = cast(GithubPullRequestConfig, event.resource_config)

    repo_options = ListRepositoryOptions(
        type=cast(GithubPortAppConfig, event.port_app_config).repository_type
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
    config = cast(GithubIssueConfig, event.resource_config)

    repo_options = ListRepositoryOptions(
        type=cast(GithubPortAppConfig, event.port_app_config).repository_type
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


@ocean.on_resync(ObjectKind.RELEASE)
async def resync_releases(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all releases in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    repository_exporter = RestRepositoryExporter(rest_client)
    release_exporter = RestReleaseExporter(rest_client)

    repo_options = ListRepositoryOptions(
        type=cast(GithubPortAppConfig, event.port_app_config).repository_type
    )

    async for repositories in repository_exporter.get_paginated_resources(repo_options):
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

    repo_options = ListRepositoryOptions(
        type=cast(GithubPortAppConfig, event.port_app_config).repository_type
    )

    async for repositories in repository_exporter.get_paginated_resources(repo_options):
        tasks = [
            tag_exporter.get_paginated_resources(ListTagOptions(repo_name=repo["name"]))
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

    repo_options = ListRepositoryOptions(
        type=cast(GithubPortAppConfig, event.port_app_config).repository_type
    )

    async for repositories in repository_exporter.get_paginated_resources(repo_options):
        tasks = [
            branch_exporter.get_paginated_resources(
                ListBranchOptions(repo_name=repo["name"])
            )
            for repo in repositories
        ]
        async for branches in stream_async_iterators_tasks(*tasks):
            yield branches


@ocean.on_resync(ObjectKind.ENVIRONMENT)
async def resync_environments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all environments in the organization."""
    logger.info(f"Starting resync for kind {kind}")

    rest_client = create_github_client()
    repository_exporter = RestRepositoryExporter(rest_client)
    environment_exporter = RestEnvironmentExporter(rest_client)

    repo_options = ListRepositoryOptions(
        type=cast(GithubPortAppConfig, event.port_app_config).repository_type
    )

    async for repositories in repository_exporter.get_paginated_resources(repo_options):
        tasks = [
            environment_exporter.get_paginated_resources(
                ListEnvironmentsOptions(
                    repo_name=repo["name"],
                )
            )
            for repo in repositories
        ]
        async for environments in stream_async_iterators_tasks(*tasks):
            yield environments


@ocean.on_resync(ObjectKind.DEPLOYMENT)
async def resync_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all deployments in the organization."""
    logger.info(f"Starting resync for kind {kind}")

    rest_client = create_github_client()
    repository_exporter = RestRepositoryExporter(rest_client)
    deployment_exporter = RestDeploymentExporter(rest_client)

    repo_options = ListRepositoryOptions(
        type=cast(GithubPortAppConfig, event.port_app_config).repository_type
    )

    async for repositories in repository_exporter.get_paginated_resources(repo_options):
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


@ocean.on_resync(ObjectKind.DEPENDABOT_ALERT)
async def resync_dependabot_alerts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all Dependabot alerts in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    repository_exporter = RestRepositoryExporter(rest_client)
    dependabot_alert_exporter = RestDependabotAlertExporter(rest_client)

    config = cast(GithubDependabotAlertConfig, event.resource_config)
    repo_options = ListRepositoryOptions(
        type=cast(GithubPortAppConfig, event.port_app_config).repository_type
    )

    async for repositories in repository_exporter.get_paginated_resources(repo_options):
        tasks = [
            dependabot_alert_exporter.get_paginated_resources(
                ListDependabotAlertOptions(
                    repo_name=repo["name"],
                    state=list(config.selector.states),
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
    repo_options = ListRepositoryOptions(
        type=cast(GithubPortAppConfig, event.port_app_config).repository_type
    )

    async for repositories in repository_exporter.get_paginated_resources(repo_options):
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


# Register webhook processors
register_live_events_webhooks(path="/webhook")
