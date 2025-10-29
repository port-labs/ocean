from typing import Any, cast

from loguru import logger
from github.actions.registry import register_actions_executors
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import stream_async_iterators_tasks

from github.core.exporters.team_exporter import (
    GraphQLTeamWithMembersExporter,
    RestTeamExporter,
)
from github.core.exporters.user_exporter import GraphQLUserExporter
from github.webhook.registry import register_live_events_webhooks
from github.core.exporters.file_exporter.utils import (
    group_file_patterns_by_repositories_in_selector,
)
from github.clients.client_factory import (
    GitHubAuthenticatorFactory,
    create_github_client,
)
from github.core.exporters.workflow_runs_exporter import RestWorkflowRunExporter
from github.clients.utils import get_github_organizations, integration_config
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.exporters.branch_exporter import RestBranchExporter
from github.core.exporters.deployment_exporter import RestDeploymentExporter
from github.core.exporters.environment_exporter import RestEnvironmentExporter
from github.core.exporters.file_exporter import RestFileExporter
from github.core.exporters.issue_exporter import RestIssueExporter
from github.core.exporters.pull_request_exporter import RestPullRequestExporter
from github.core.exporters.repository_exporter import (
    RestRepositoryExporter,
)
from github.core.exporters.release_exporter import RestReleaseExporter
from github.core.exporters.tag_exporter import RestTagExporter
from github.core.exporters.dependabot_exporter import RestDependabotAlertExporter
from github.core.exporters.code_scanning_alert_exporter import (
    RestCodeScanningAlertExporter,
)
from github.core.exporters.secret_scanning_alert_exporter import (
    RestSecretScanningAlertExporter,
)
from github.core.exporters.collaborator_exporter import RestCollaboratorExporter
from github.core.exporters.folder_exporter import (
    RestFolderExporter,
    create_path_mapping,
)
from github.core.exporters.workflows_exporter import RestWorkflowExporter
from github.core.exporters.organization_exporter import RestOrganizationExporter

from github.core.options import (
    ListBranchOptions,
    ListDeploymentsOptions,
    ListEnvironmentsOptions,
    ListFolderOptions,
    ListIssueOptions,
    ListPullRequestOptions,
    ListRepositoryOptions,
    ListTeamOptions,
    ListUserOptions,
    ListWorkflowOptions,
    ListWorkflowRunOptions,
    ListReleaseOptions,
    ListTagOptions,
    ListDependabotAlertOptions,
    ListCodeScanningAlertOptions,
    ListCollaboratorOptions,
    ListSecretScanningAlertOptions,
)
from github.helpers.utils import ObjectKind, GithubClientType
from github.webhook.events import WEBHOOK_CREATE_EVENTS
from github.webhook.webhook_client import GithubWebhookClient

from integration import (
    GithubFolderResourceConfig,
    GithubIssueConfig,
    GithubPortAppConfig,
    GithubPullRequestConfig,
    GithubDependabotAlertConfig,
    GithubCodeScanningAlertConfig,
    GithubRepositoryConfig,
    GithubTeamConfig,
    GithubFileResourceConfig,
    GithubBranchConfig,
    GithubSecretScanningAlertConfig,
)


@ocean.on_resync_start()
async def on_resync_start() -> None:
    """Initialize the integration and set up webhooks."""
    logger.info("Setting up webhooks for GitHub organizations")

    if not ocean.app.config.event_listener.should_create_webhooks_if_enabled:
        logger.info(
            "Skipping webhook creation as it's not supported for this event listener"
        )
        return

    base_url = ocean.app.base_url
    if not base_url:
        return

    org_exporter = RestOrganizationExporter(create_github_client())

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        logger.info(
            f"Subscribing to GitHub webhooks for {len(organizations)} organizations"
        )

        for org in organizations:
            org_name = org["login"]

            authenticator = GitHubAuthenticatorFactory.create(
                github_host=ocean.integration_config["github_host"],
                organization=org_name,
                token=ocean.integration_config.get("github_token"),
                app_id=ocean.integration_config.get("github_app_id"),
                private_key=ocean.integration_config.get("github_app_private_key"),
            )

            client = GithubWebhookClient(
                **integration_config(authenticator),
                organization=org_name,
                webhook_secret=ocean.integration_config["webhook_secret"],
            )

            logger.info(f"Subscribing to GitHub webhooks for organization: {org_name}")
            await client.upsert_webhook(base_url, WEBHOOK_CREATE_EVENTS)


@ocean.on_resync(ObjectKind.ORGANIZATION)
async def resync_organizations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all organizations the Personal Access Token user is a member of."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    exporter = RestOrganizationExporter(rest_client)

    async for organizations in exporter.get_paginated_resources(
        get_github_organizations()
    ):
        logger.info(f"Received {len(organizations)} batch {kind}s")
        yield organizations


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all repositories across organizations."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    org_exporter = RestOrganizationExporter(rest_client)
    port_app_config = cast(GithubPortAppConfig, event.port_app_config)

    repo_config = cast(GithubRepositoryConfig, event.resource_config)
    included_relationships = repo_config.selector.include

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = (
            RestRepositoryExporter(rest_client).get_paginated_resources(
                options=ListRepositoryOptions(
                    organization=org["login"],
                    type=port_app_config.repository_type,
                    included_relationships=cast(list[str], included_relationships),
                )
            )
            for org in organizations
        )
        async for repositories in stream_async_iterators_tasks(*tasks):
            yield repositories


@ocean.on_resync(ObjectKind.USER)
async def resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all users across organizations."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    graphql_client = create_github_client(GithubClientType.GRAPHQL)
    org_exporter = RestOrganizationExporter(rest_client)

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = (
            GraphQLUserExporter(graphql_client).get_paginated_resources(
                options=ListUserOptions(organization=org["login"])
            )
            for org in organizations
        )
        async for users in stream_async_iterators_tasks(*tasks):
            yield users


@ocean.on_resync(ObjectKind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all teams across organizations."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    graphql_client = create_github_client(GithubClientType.GRAPHQL)

    org_exporter = RestOrganizationExporter(rest_client)

    config = cast(GithubTeamConfig, event.resource_config)
    selector = config.selector

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = []
        for org in organizations:
            org_name = org["login"]
            exporter: AbstractGithubExporter[Any]

            if selector.members:
                exporter = GraphQLTeamWithMembersExporter(graphql_client)
            else:
                exporter = RestTeamExporter(rest_client)

            tasks.append(
                exporter.get_paginated_resources(ListTeamOptions(organization=org_name))
            )

        async for teams in stream_async_iterators_tasks(*tasks):
            yield teams


@ocean.on_resync(ObjectKind.WORKFLOW)
async def resync_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all workflows for specified Github repositories"""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    org_exporter = RestOrganizationExporter(rest_client)
    port_app_config = cast(GithubPortAppConfig, event.port_app_config)

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = []
        for org in organizations:
            org_name = org["login"]
            repo_exporter = RestRepositoryExporter(rest_client)
            workflow_exporter = RestWorkflowExporter(rest_client)

            repo_options = ListRepositoryOptions(
                organization=org_name, type=port_app_config.repository_type
            )

            async for repositories in repo_exporter.get_paginated_resources(
                options=repo_options
            ):
                for repo in repositories:
                    tasks.append(
                        workflow_exporter.get_paginated_resources(
                            options=ListWorkflowOptions(
                                organization=org_name, repo_name=repo["name"]
                            )
                        )
                    )

        async for workflows in stream_async_iterators_tasks(*tasks):
            yield workflows


@ocean.on_resync(ObjectKind.WORKFLOW_RUN)
async def resync_workflow_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all workflow runs for specified Github repositories"""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    org_exporter = RestOrganizationExporter(rest_client)
    repo_exporter = RestRepositoryExporter(rest_client)
    workflow_exporter = RestWorkflowExporter(rest_client)
    workflow_run_exporter = RestWorkflowRunExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = []
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name, type=port_app_config.repository_type
            )

            async for repositories in repo_exporter.get_paginated_resources(
                options=repo_options
            ):
                for repo in repositories:
                    repo_name = repo["name"]
                    workflow_options = ListWorkflowOptions(
                        organization=org_name, repo_name=repo_name
                    )
                    async for workflows in workflow_exporter.get_paginated_resources(
                        workflow_options
                    ):
                        tasks = [
                            workflow_run_exporter.get_paginated_resources(
                                ListWorkflowRunOptions(
                                    organization=org_name,
                                    repo_name=repo_name,
                                    workflow_id=workflow["id"],
                                    max_runs=100,
                                )
                            )
                            for workflow in workflows
                        ]

                        async for runs in stream_async_iterators_tasks(*tasks):
                            yield runs


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all pull requests in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    pull_request_exporter = RestPullRequestExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)

    config = cast(GithubPullRequestConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = []
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name, type=port_app_config.repository_type
            )

            async for repos in repository_exporter.get_paginated_resources(
                options=repo_options
            ):
                for repo in repos:
                    tasks.append(
                        pull_request_exporter.get_paginated_resources(
                            ListPullRequestOptions(
                                organization=org_name,
                                repo_name=repo["name"],
                                states=list(config.selector.states),
                                max_results=config.selector.max_results,
                                since=config.selector.since,
                            )
                        )
                    )

        async for pull_requests in stream_async_iterators_tasks(*tasks):
            yield pull_requests


@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all issues from repositories."""
    logger.info(f"Starting resync for kind {kind}")

    rest_client = create_github_client()
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    issue_exporter = RestIssueExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)

    config = cast(GithubIssueConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = []
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name, type=port_app_config.repository_type
            )

            async for repos in repository_exporter.get_paginated_resources(
                options=repo_options
            ):
                for repo in repos:
                    tasks.append(
                        issue_exporter.get_paginated_resources(
                            ListIssueOptions(
                                organization=org_name,
                                repo_name=repo["name"],
                                state=config.selector.state,
                            )
                        )
                    )

        async for issues in stream_async_iterators_tasks(*tasks):
            yield issues


@ocean.on_resync(ObjectKind.RELEASE)
async def resync_releases(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all releases in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    release_exporter = RestReleaseExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = []
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name, type=port_app_config.repository_type
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                for repo in repositories:
                    tasks.append(
                        release_exporter.get_paginated_resources(
                            ListReleaseOptions(
                                organization=org_name, repo_name=repo["name"]
                            )
                        )
                    )

        async for releases in stream_async_iterators_tasks(*tasks):
            yield releases


@ocean.on_resync(ObjectKind.TAG)
async def resync_tags(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all tags in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    tag_exporter = RestTagExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = []
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name, type=port_app_config.repository_type
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                for repo in repositories:
                    tasks.append(
                        tag_exporter.get_paginated_resources(
                            ListTagOptions(
                                organization=org_name, repo_name=repo["name"]
                            )
                        )
                    )

        async for tags in stream_async_iterators_tasks(*tasks):
            yield tags


@ocean.on_resync(ObjectKind.BRANCH)
async def resync_branches(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all branches in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    branch_exporter = RestBranchExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)

    selector = cast(GithubBranchConfig, event.resource_config).selector

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = []
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name, type=port_app_config.repository_type
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                for repo in repositories:
                    tasks.append(
                        branch_exporter.get_paginated_resources(
                            ListBranchOptions(
                                organization=org_name,
                                repo_name=repo["name"],
                                detailed=selector.detailed,
                                protection_rules=selector.protection_rules,
                            )
                        )
                    )

        async for branches in stream_async_iterators_tasks(*tasks):
            yield branches


@ocean.on_resync(ObjectKind.ENVIRONMENT)
async def resync_environments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all environments in the organization."""
    logger.info(f"Starting resync for kind {kind}")

    rest_client = create_github_client()
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    environment_exporter = RestEnvironmentExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = []
        for org in organizations:
            org_name = org["login"]

            repo_options = ListRepositoryOptions(
                organization=org_name, type=port_app_config.repository_type
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                for repo in repositories:
                    tasks.append(
                        environment_exporter.get_paginated_resources(
                            ListEnvironmentsOptions(
                                organization=org_name,
                                repo_name=repo["name"],
                            )
                        )
                    )

        async for environments in stream_async_iterators_tasks(*tasks):
            yield environments


@ocean.on_resync(ObjectKind.DEPLOYMENT)
async def resync_deployments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all deployments in the organization."""
    logger.info(f"Starting resync for kind {kind}")

    rest_client = create_github_client()
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    deployment_exporter = RestDeploymentExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = []
        for org in organizations:
            org_name = org["login"]

            repo_options = ListRepositoryOptions(
                organization=org_name, type=port_app_config.repository_type
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                for repo in repositories:
                    tasks.append(
                        deployment_exporter.get_paginated_resources(
                            ListDeploymentsOptions(
                                organization=org_name,
                                repo_name=repo["name"],
                            )
                        )
                    )

        async for deployments in stream_async_iterators_tasks(*tasks):
            yield deployments


@ocean.on_resync(ObjectKind.DEPENDABOT_ALERT)
async def resync_dependabot_alerts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all Dependabot alerts in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    dependabot_alert_exporter = RestDependabotAlertExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)

    config = cast(GithubDependabotAlertConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = []
        for org in organizations:
            org_name = org["login"]

            repo_options = ListRepositoryOptions(
                organization=org_name, type=port_app_config.repository_type
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                for repo in repositories:
                    tasks.append(
                        dependabot_alert_exporter.get_paginated_resources(
                            ListDependabotAlertOptions(
                                organization=org_name,
                                repo_name=repo["name"],
                                state=list(config.selector.states),
                            )
                        )
                    )

        async for alerts in stream_async_iterators_tasks(*tasks):
            yield alerts


@ocean.on_resync(ObjectKind.CODE_SCANNING_ALERT)
async def resync_code_scanning_alerts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all code scanning alerts in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    code_scanning_alert_exporter = RestCodeScanningAlertExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)

    config = cast(GithubCodeScanningAlertConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = []
        for org in organizations:
            org_name = org["login"]

            repo_options = ListRepositoryOptions(
                organization=org_name, type=port_app_config.repository_type
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                for repo in repositories:
                    tasks.append(
                        code_scanning_alert_exporter.get_paginated_resources(
                            ListCodeScanningAlertOptions(
                                organization=org_name,
                                repo_name=repo["name"],
                                state=config.selector.state,
                            )
                        )
                    )

        async for alerts in stream_async_iterators_tasks(*tasks):
            yield alerts


@ocean.on_resync(ObjectKind.FOLDER)
async def resync_folders(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all folders in specified repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    folder_exporter = RestFolderExporter(rest_client)

    selector = cast(GithubFolderResourceConfig, event.resource_config).selector
    if not selector.folders:
        logger.info(
            "Skipping folder kind resync because required selectors are missing"
        )
        return

    repo_path_map = create_path_mapping(selector.folders)
    folder_options = ListFolderOptions(repo_mapping=repo_path_map)

    async for folders in folder_exporter.get_paginated_resources(folder_options):
        yield folders


@ocean.on_resync(ObjectKind.FILE)
async def resync_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync files based on configuration using the file exporter."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    file_exporter = RestFileExporter(rest_client)
    repo_exporter = RestRepositoryExporter(rest_client)

    config = cast(GithubFileResourceConfig, event.resource_config)
    app_config = cast(GithubPortAppConfig, event.port_app_config)
    files_pattern = config.selector.files

    repo_path_map = await group_file_patterns_by_repositories_in_selector(
        files_pattern, repo_exporter, app_config.repository_type
    )

    async for file_results in file_exporter.get_paginated_resources(repo_path_map):
        yield file_results


@ocean.on_resync(ObjectKind.COLLABORATOR)
async def resync_collaborators(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all collaborators in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    collaborator_exporter = RestCollaboratorExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = []
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name, type=port_app_config.repository_type
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                for repo in repositories:
                    tasks.append(
                        collaborator_exporter.get_paginated_resources(
                            ListCollaboratorOptions(
                                organization=org_name, repo_name=repo["name"]
                            )
                        )
                    )

        async for collaborators in stream_async_iterators_tasks(*tasks):
            yield collaborators


@ocean.on_resync(ObjectKind.SECRET_SCANNING_ALERT)
async def resync_secret_scanning_alerts(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all secret scanning alerts in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client()
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    secret_scanning_alert_exporter = RestSecretScanningAlertExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)

    config = cast(GithubSecretScanningAlertConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources(
        get_github_organizations()
    ):
        tasks = []
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name, type=port_app_config.repository_type
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                for repo in repositories:
                    tasks.append(
                        secret_scanning_alert_exporter.get_paginated_resources(
                            ListSecretScanningAlertOptions(
                                organization=org_name,
                                repo_name=repo["name"],
                                state=config.selector.state,
                                hide_secret=config.selector.hide_secret,
                            )
                        )
                    )

        async for alerts in stream_async_iterators_tasks(*tasks):
            yield alerts


# Register webhook processors
register_live_events_webhooks()

# Register actions executors
register_actions_executors()
