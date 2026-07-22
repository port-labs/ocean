import asyncio
from typing import Any, Callable, cast

from loguru import logger

from github.actions.registry import register_actions_executors
from github.clients.auth import get_auth_provider
from github.clients.auth.abstract_authenticator import (
    AbstractGitHubAuthenticator,
)
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import (
    semaphore_async_iterator,
    stream_async_iterators_tasks,
    stream_independent_async_iterators,
)

from github.core.exporters.team_exporter import (
    GraphQLTeamWithMembersExporter,
    RestTeamExporter,
)
from github.core.exporters.user_exporter import GraphQLUserExporter
from github.webhook.registry import register_live_events_webhooks
from github.core.exporters.file_exporter.utils import FilePatternMappingBuilder
from github.clients.client_factory import (
    create_github_client,
)
from github.webhook.clients.client_factory import GithubWebhookClientFactory
from github.core.exporters.workflow_runs_exporter import RestWorkflowRunExporter
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.exporters.branch_exporter import RestBranchExporter
from github.core.exporters.deployment_exporter import RestDeploymentExporter
from github.core.exporters.deployment_status_exporter import (
    RestDeploymentStatusExporter,
)
from github.core.exporters.environment_exporter import RestEnvironmentExporter
from github.core.exporters.file_exporter import RestFileExporter
from github.core.exporters.issue_exporter import RestIssueExporter
from github.core.exporters.pull_request_exporter import (
    GraphQLPullRequestExporter,
    RestPullRequestExporter,
)
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
    FolderPatternMappingBuilder,
)
from github.core.exporters.workflows_exporter import RestWorkflowExporter
from github.core.exporters.organization_exporter import RestOrganizationExporter
from github.clients.utils import can_access_organization

from github.core.options import (
    ListBranchOptions,
    ListDeploymentsOptions,
    ListDeploymentStatusesOptions,
    ListEnvironmentsOptions,
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
from github.helpers.utils import (
    ObjectKind,
    GithubClientType,
    enrich_members_with_saml_email,
    enrich_user_with_primary_email,
    tag_batch_with_org,
)

from integration import (
    GithubCollaboratorConfig,
    GithubEnvironmentConfig,
    GithubFolderResourceConfig,
    GithubReleaseConfig,
    GithubIssueConfig,
    GithubPortAppConfig,
    GithubPullRequestConfig,
    GithubDependabotAlertConfig,
    GithubCodeScanningAlertConfig,
    GithubRepositoryConfig,
    GithubTagConfig,
    GithubTeamConfig,
    GithubFileResourceConfig,
    GithubBranchConfig,
    GithubSecretScanningAlertConfig,
    GithubDeploymentConfig,
    GithubDeploymentStatusConfig,
    GithubWorkflowConfig,
    GithubWorkflowRunConfig,
    GithubUserConfig,
)
from github.enrichments.included_files import (
    IncludedFilesEnricher,
    FileIncludedFilesStrategy,
    FolderIncludedFilesStrategy,
    RepositoryIncludedFilesStrategy,
)

MAX_CONCURRENT_REPOS = 10
MAX_CONCURRENT_AUTHENTICATORS = 10


async def _create_webhooks_for_organization(org_name: str, base_url: str) -> None:
    webhook_secret = ocean.integration_config["webhook_secret"]
    skip_patching = ocean.integration_config["skip_webhook_patching"]
    authenticator = await get_auth_provider().get_authenticator_for_organization(
        org_name
    )

    client = await GithubWebhookClientFactory.create(
        authenticator=authenticator,
        organization=org_name,
        webhook_secret=webhook_secret,
        skip_patching=skip_patching,
    )

    logger.info(f"Subscribing to GitHub webhooks for organization: {org_name}")
    await client.upsert_webhook(base_url)


@ocean.on_start()
async def on_start() -> None:
    """Initialize the integration and set up webhooks."""
    if not ocean.app.config.event_listener.should_process_webhooks:
        logger.info(
            "Skipping webhook creation as it's not supported for this event listener"
        )
        return

    base_url = ocean.app.base_url
    if not base_url:
        return

    github_organization = ocean.integration_config.get("github_organization")
    if github_organization:
        await _create_webhooks_for_organization(github_organization, base_url)
        return

    await ocean.integration.port_app_config_handler.get_port_app_config()
    for authenticator in await get_auth_provider().list_authenticators():
        rest_client = create_github_client(authenticator)
        org_exporter = RestOrganizationExporter(rest_client)
        async for organizations in org_exporter.get_paginated_resources():
            logger.info(
                f"Subscribing to GitHub webhooks for {len(organizations)} organizations"
            )

            for org in organizations:
                await _create_webhooks_for_organization(org["login"], base_url)


def _resync_per_authenticator(
    resync: Callable[
        [str, AbstractGitHubAuthenticator],
        ASYNC_GENERATOR_RESYNC_TYPE,
    ],
) -> Callable[[str], ASYNC_GENERATOR_RESYNC_TYPE]:
    async def wrapper(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
        logger.info(f"Starting resync for kind: {kind}")
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_AUTHENTICATORS)

        def build_authenticator_iterator(
            authenticator: AbstractGitHubAuthenticator,
        ) -> Callable[[], ASYNC_GENERATOR_RESYNC_TYPE]:
            def iterator() -> ASYNC_GENERATOR_RESYNC_TYPE:
                return resync(kind, authenticator)

            return iterator

        tasks = (
            semaphore_async_iterator(
                semaphore,
                build_authenticator_iterator(authenticator),
            )
            for authenticator in await get_auth_provider().list_authenticators()
        )
        async for result in stream_independent_async_iterators(*tasks, context=kind):
            yield result

    return wrapper


@ocean.on_resync(ObjectKind.ORGANIZATION)
@_resync_per_authenticator
async def resync_organizations(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all organizations the Personal Access Token user is a member of."""

    rest_client = create_github_client(authenticator)
    exporter = RestOrganizationExporter(rest_client)

    async for organizations in exporter.get_paginated_resources():
        logger.info(f"Received {len(organizations)} batch {kind}s")
        yield organizations


@ocean.on_resync(ObjectKind.REPOSITORY)
@_resync_per_authenticator
async def resync_repositories(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all repositories across organizations."""

    rest_client = create_github_client(authenticator)
    org_exporter = RestOrganizationExporter(rest_client)
    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    repo_config = cast(GithubRepositoryConfig, event.resource_config)
    included_relations = repo_config.selector.normalized_relations
    included_files = repo_config.selector.included_files or []
    included_files_enricher = (
        IncludedFilesEnricher(
            client=rest_client,
            strategy=RepositoryIncludedFilesStrategy(included_files=included_files),
        )
        if included_files
        else None
    )

    async for organizations in org_exporter.get_paginated_resources():
        tasks = (
            RestRepositoryExporter(rest_client).get_paginated_resources(
                options=ListRepositoryOptions(
                    organization=org["login"],
                    organization_type=org["type"],
                    type=port_app_config.repository_type,
                    included_relations=included_relations,
                    search_params=repo_config.selector.repo_search,
                )
            )
            for org in organizations
        )
        async for repositories in stream_async_iterators_tasks(*tasks):
            if included_files_enricher:
                repositories = await included_files_enricher.enrich_batch(repositories)
            yield repositories


@ocean.on_resync(ObjectKind.USER)
@_resync_per_authenticator
async def resync_users(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all users across organizations."""

    rest_client = create_github_client(authenticator)
    graphql_client = create_github_client(authenticator, GithubClientType.GRAPHQL)
    org_exporter = RestOrganizationExporter(rest_client)
    exporter = GraphQLUserExporter(graphql_client)
    config = cast(GithubUserConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources():
        tasks = []
        for org in organizations:
            if org["type"] == "Organization":
                tasks.append(
                    exporter.get_paginated_resources(
                        options=ListUserOptions(
                            organization=org["login"],
                            include_saml_email=config.selector.include_saml_email,
                        )
                    )
                )
                continue

            if not org.get("email"):
                org = await enrich_user_with_primary_email(rest_client, org)
            yield [org]

        if tasks:
            async for users in stream_async_iterators_tasks(*tasks):
                yield users


@ocean.on_resync(ObjectKind.TEAM)
@_resync_per_authenticator
async def resync_teams(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all teams across organizations."""

    rest_client = create_github_client(authenticator)
    graphql_client = create_github_client(authenticator, GithubClientType.GRAPHQL)

    org_exporter = RestOrganizationExporter(rest_client)

    config = cast(GithubTeamConfig, event.resource_config)
    selector = config.selector

    async for organizations in org_exporter.get_paginated_resources():
        tasks = []
        for org in organizations:
            if org["type"] == "Organization":
                org_name = org["login"]
                rest_exporter = RestTeamExporter(rest_client)

                tasks.append(
                    tag_batch_with_org(
                        org_name,
                        rest_exporter.get_paginated_resources(
                            ListTeamOptions(organization=org_name)
                        ),
                    )
                )

        if tasks:
            async for org_name, teams in stream_async_iterators_tasks(*tasks):
                if selector.members:
                    graphql_exporter = GraphQLTeamWithMembersExporter(graphql_client)
                    teams = await graphql_exporter._enrich_team_with_extras(
                        teams,
                        ListTeamOptions(
                            organization=org_name,
                            include_saml_email=selector.include_saml_email,
                        ),
                    )
                    teams = await RestTeamExporter(
                        rest_client
                    ).enrich_enterprise_teams_with_members(teams, org_name)
                    for team in teams:
                        if team["slug"].startswith("ent:"):
                            await enrich_members_with_saml_email(
                                graphql_client,
                                org_name,
                                team["members"]["nodes"],
                                selector.include_saml_email,
                            )

                yield teams


@ocean.on_resync(ObjectKind.WORKFLOW)
@_resync_per_authenticator
async def resync_workflows(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all workflows for specified Github repositories"""

    rest_client = create_github_client(authenticator)
    org_exporter = RestOrganizationExporter(rest_client)
    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    config = cast(GithubWorkflowConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources():
        for org in organizations:
            org_name = org["login"]
            repo_exporter = RestRepositoryExporter(rest_client)
            workflow_exporter = RestWorkflowExporter(rest_client)

            repo_options = ListRepositoryOptions(
                organization=org_name,
                organization_type=org["type"],
                type=port_app_config.repository_type,
                search_params=config.selector.repo_search,
            )

            async for repositories in repo_exporter.get_paginated_resources(
                options=repo_options
            ):
                tasks = []
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
@_resync_per_authenticator
async def resync_workflow_runs(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all workflow runs for specified Github repositories"""

    rest_client = create_github_client(authenticator)
    org_exporter = RestOrganizationExporter(rest_client)
    repo_exporter = RestRepositoryExporter(rest_client)
    workflow_exporter = RestWorkflowExporter(rest_client)
    workflow_run_exporter = RestWorkflowRunExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    config = cast(GithubWorkflowRunConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources():
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name,
                organization_type=org["type"],
                type=port_app_config.repository_type,
                search_params=config.selector.repo_search,
            )

            async for repositories in repo_exporter.get_paginated_resources(
                options=repo_options
            ):
                tasks = []
                for repo in repositories:
                    repo_name = repo["name"]
                    workflow_options = ListWorkflowOptions(
                        organization=org_name, repo_name=repo_name
                    )
                    async for workflows in workflow_exporter.get_paginated_resources(
                        workflow_options
                    ):
                        if config.selector.statuses:
                            tasks = [
                                workflow_run_exporter.get_paginated_resources(
                                    ListWorkflowRunOptions(
                                        organization=org_name,
                                        repo_name=repo_name,
                                        workflow_id=workflow["id"],
                                        max_runs=100,
                                        status=status,
                                        created=config.selector.created_after,
                                    )
                                )
                                for workflow in workflows
                                for status in config.selector.statuses
                            ]
                        else:
                            tasks = [
                                workflow_run_exporter.get_paginated_resources(
                                    ListWorkflowRunOptions(
                                        organization=org_name,
                                        repo_name=repo_name,
                                        workflow_id=workflow["id"],
                                        max_runs=100,
                                        created=config.selector.created_after,
                                    )
                                )
                                for workflow in workflows
                            ]

                    async for runs in stream_async_iterators_tasks(*tasks):
                        yield runs


@ocean.on_resync(ObjectKind.PULL_REQUEST)
@_resync_per_authenticator
async def resync_pull_requests(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all pull requests in the organization's repositories."""

    rest_client = create_github_client(authenticator)
    graphql_client = create_github_client(authenticator, GithubClientType.GRAPHQL)
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    config = cast(GithubPullRequestConfig, event.resource_config)

    is_graphql_api = config.selector.api == GithubClientType.GRAPHQL
    pull_request_exporter: AbstractGithubExporter[Any] = (
        GraphQLPullRequestExporter(graphql_client)
        if is_graphql_api
        else RestPullRequestExporter(rest_client)
    )

    fetch_errors: list[Exception] = []

    async for organizations in org_exporter.get_paginated_resources():
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name,
                organization_type=org["type"],
                type=port_app_config.repository_type,
                search_params=config.selector.repo_search,
            )

            async for repos in repository_exporter.get_paginated_resources(
                options=repo_options
            ):
                tasks = []
                for repo in repos:
                    tasks.append(
                        pull_request_exporter.get_paginated_resources(
                            ListPullRequestOptions(
                                organization=org_name,
                                repo_name=repo["name"],
                                states=list(config.selector.states),
                                max_results=config.selector.effective_max_results,
                                updated_after=config.selector.updated_after,
                                closed_after=config.selector.closed_after,
                                enrich_with_first_commit=config.selector.enrich_with_first_commit,
                                repo=repo if is_graphql_api else None,
                                exclude_graphql_fields=config.selector.exclude_graphql_fields,
                            )
                        )
                    )

                try:
                    async for pull_requests in stream_independent_async_iterators(
                        *tasks, context=kind
                    ):
                        yield pull_requests
                except ExceptionGroup as page_errors:
                    fetch_errors.extend(page_errors.exceptions)
                    logger.error(
                        f"{len(page_errors.exceptions)} repo(s) failed fetching pull requests "
                        f"in org {org_name} (batch of {len(repos)}), continuing with remaining pages",
                        extra={
                            "failed_repos": [
                                str(error) for error in page_errors.exceptions
                            ],
                        },
                    )

    if fetch_errors:
        raise ExceptionGroup(
            f"{kind} failed with {len(fetch_errors)} error(s)",
            fetch_errors,
        )


@ocean.on_resync(ObjectKind.ISSUE)
@_resync_per_authenticator
async def resync_issues(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all issues from repositories."""

    rest_client = create_github_client(authenticator)
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    issue_exporter = RestIssueExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    config = cast(GithubIssueConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources():
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name,
                organization_type=org["type"],
                type=port_app_config.repository_type,
                search_params=config.selector.repo_search,
            )

            async for repos in repository_exporter.get_paginated_resources(
                options=repo_options
            ):
                tasks = []
                for repo in repos:
                    tasks.append(
                        issue_exporter.get_paginated_resources(
                            ListIssueOptions(
                                organization=org_name,
                                repo_name=repo["name"],
                                state=config.selector.state,
                                labels=config.selector.labels_str,
                            )
                        )
                    )

                async for issues in stream_async_iterators_tasks(*tasks):
                    yield issues


@ocean.on_resync(ObjectKind.RELEASE)
@_resync_per_authenticator
async def resync_releases(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all releases in the organization's repositories."""

    rest_client = create_github_client(authenticator)
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    release_exporter = RestReleaseExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    config = cast(GithubReleaseConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources():
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name,
                organization_type=org["type"],
                type=port_app_config.repository_type,
                search_params=config.selector.repo_search,
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                tasks = []
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
@_resync_per_authenticator
async def resync_tags(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all tags in the organization's repositories."""

    rest_client = create_github_client(authenticator)
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    tag_exporter = RestTagExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    config = cast(GithubTagConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources():
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name,
                organization_type=org["type"],
                type=port_app_config.repository_type,
                search_params=config.selector.repo_search,
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                tasks = []
                for repo in repositories:
                    tasks.append(
                        tag_exporter.get_paginated_resources(
                            ListTagOptions(
                                organization=org_name, repo_name=repo["name"], repo=repo
                            )
                        )
                    )

                async for tags in stream_async_iterators_tasks(*tasks):
                    yield tags


@ocean.on_resync(ObjectKind.BRANCH)
@_resync_per_authenticator
async def resync_branches(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all branches in the organization's repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    rest_client = create_github_client(authenticator)
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    branch_exporter = RestBranchExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    selector = cast(GithubBranchConfig, event.resource_config).selector

    async for organizations in org_exporter.get_paginated_resources():
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name,
                organization_type=org["type"],
                type=port_app_config.repository_type,
                search_params=selector.repo_search,
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                tasks = []
                for repo in repositories:
                    tasks.append(
                        branch_exporter.get_paginated_resources(
                            ListBranchOptions(
                                organization=org_name,
                                repo_name=repo["name"],
                                protection_rules=selector.protection_rules,
                                detailed=selector.detailed,
                                branch_names=selector.branch_names,
                                default_branch_only=selector.default_branch_only,
                                repo=repo,
                            )
                        )
                    )

                    if len(tasks) == MAX_CONCURRENT_REPOS:
                        async for branches in stream_async_iterators_tasks(*tasks):
                            yield branches
                        tasks.clear()

                if tasks:
                    async for branches in stream_async_iterators_tasks(*tasks):
                        yield branches


@ocean.on_resync(ObjectKind.ENVIRONMENT)
@_resync_per_authenticator
async def resync_environments(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all environments in the organization."""
    logger.info(f"Starting resync for kind {kind}")

    rest_client = create_github_client(authenticator)
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    environment_exporter = RestEnvironmentExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    config = cast(GithubEnvironmentConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources():
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name,
                organization_type=org["type"],
                type=port_app_config.repository_type,
                search_params=config.selector.repo_search,
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                tasks = []
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
@_resync_per_authenticator
async def resync_deployments(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all deployments in the organization."""
    logger.info(f"Starting resync for kind {kind}")

    rest_client = create_github_client(authenticator)
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    deployment_exporter = RestDeploymentExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    config = cast(GithubDeploymentConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources():
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name,
                organization_type=org["type"],
                type=port_app_config.repository_type,
                search_params=config.selector.repo_search,
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                tasks = []
                for repo in repositories:
                    tasks.append(
                        deployment_exporter.get_paginated_resources(
                            ListDeploymentsOptions(
                                organization=org_name,
                                repo_name=repo["name"],
                                task=config.selector.task,
                                environment=config.selector.environment,
                                enrich_with_first_commit=config.selector.enrich_with_first_commit,
                            )
                        )
                    )

                async for deployments in stream_async_iterators_tasks(*tasks):
                    yield deployments


@ocean.on_resync(ObjectKind.DEPLOYMENT_STATUS)
@_resync_per_authenticator
async def resync_deployment_statuses(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all deployment statuses in the organization."""
    logger.info(f"Starting resync for kind {kind}")

    rest_client = create_github_client(authenticator)
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    deployment_exporter = RestDeploymentExporter(rest_client)
    deployment_status_exporter = RestDeploymentStatusExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    config = cast(GithubDeploymentStatusConfig, event.resource_config)

    logger.info(
        f"Deployment status resync filters: "
        f"task={config.selector.task}, environment={config.selector.environment}"
    )

    async for organizations in org_exporter.get_paginated_resources():
        for org in organizations:
            org_name = org["login"]
            org_type = org["type"]
            logger.debug(f"Processing organization: {org_name} (type={org_type})")

            repo_options = ListRepositoryOptions(
                organization=org_name,
                organization_type=org_type,
                type=port_app_config.repository_type,
                search_params=config.selector.repo_search,
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                for repo in repositories:
                    repo_name = repo["name"]
                    logger.debug(f"Fetching deployments for {org_name}/{repo_name}")
                    deployment_options = ListDeploymentsOptions(
                        organization=org_name,
                        repo_name=repo_name,
                        task=config.selector.task,
                        environment=config.selector.environment,
                    )

                    async for (
                        deployments
                    ) in deployment_exporter.get_paginated_resources(
                        deployment_options
                    ):
                        logger.debug(
                            f"Found {len(deployments)} deployments in {org_name}/{repo_name}"
                        )
                        tasks = []
                        for deployment in deployments:
                            deployment_id = str(deployment["id"])
                            logger.debug(
                                f"Fetching statuses for deployment {deployment_id} "
                                f"(task={deployment['task']}, env={deployment['environment']})"
                            )
                            tasks.append(
                                deployment_status_exporter.get_paginated_resources(
                                    ListDeploymentStatusesOptions(
                                        organization=org_name,
                                        repo_name=repo_name,
                                        deployment_id=deployment_id,
                                    )
                                )
                            )

                        async for statuses in stream_async_iterators_tasks(*tasks):
                            yield statuses


@ocean.on_resync(ObjectKind.DEPENDABOT_ALERT)
@_resync_per_authenticator
async def resync_dependabot_alerts(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all Dependabot alerts in the organization's repositories."""

    rest_client = create_github_client(authenticator)
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    dependabot_alert_exporter = RestDependabotAlertExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    config = cast(GithubDependabotAlertConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources():
        for org in organizations:
            org_name = org["login"]

            repo_options = ListRepositoryOptions(
                organization=org_name,
                organization_type=org["type"],
                type=port_app_config.repository_type,
                search_params=config.selector.repo_search,
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                tasks = []
                for repo in repositories:
                    tasks.append(
                        dependabot_alert_exporter.get_paginated_resources(
                            ListDependabotAlertOptions(
                                organization=org_name,
                                repo_name=repo["name"],
                                state=list(config.selector.states),
                                severity=config.selector.severity_str,
                                ecosystem=config.selector.ecosystems_str,
                            )
                        )
                    )

                async for alerts in stream_async_iterators_tasks(*tasks):
                    yield alerts


@ocean.on_resync(ObjectKind.CODE_SCANNING_ALERT)
@_resync_per_authenticator
async def resync_code_scanning_alerts(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all code scanning alerts in the organization's repositories."""

    rest_client = create_github_client(authenticator)
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    code_scanning_alert_exporter = RestCodeScanningAlertExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    config = cast(GithubCodeScanningAlertConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources():
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name,
                organization_type=org["type"],
                type=port_app_config.repository_type,
                search_params=config.selector.repo_search,
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                tasks = []
                for repo in repositories:
                    tasks.append(
                        code_scanning_alert_exporter.get_paginated_resources(
                            ListCodeScanningAlertOptions(
                                organization=org_name,
                                repo_name=repo["name"],
                                state=config.selector.state,
                                severity=config.selector.severity,
                            )
                        )
                    )

                async for alerts in stream_async_iterators_tasks(*tasks):
                    yield alerts


@ocean.on_resync(ObjectKind.FOLDER)
@_resync_per_authenticator
async def resync_folders(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all folders in specified repositories."""
    logger.info(f"Starting resync for kind: {kind}")

    selector = cast(GithubFolderResourceConfig, event.resource_config).selector
    folders = [
        folder
        for folder in selector.folders
        if can_access_organization(authenticator, folder.organization)
    ]
    if not folders:
        return

    rest_client = create_github_client(authenticator)
    folder_exporter = RestFolderExporter(rest_client)
    should_enrich_with_included_files = any(
        folder_sel.included_files for folder_sel in folders
    )
    should_enrich_with_included_files = should_enrich_with_included_files or bool(
        selector.included_files
    )
    included_files_enricher = (
        IncludedFilesEnricher(
            client=rest_client,
            strategy=FolderIncludedFilesStrategy(
                folder_selectors=folders,
                global_included_files=selector.included_files,
            ),
        )
        if should_enrich_with_included_files
        else None
    )

    org_exporter = RestOrganizationExporter(rest_client)
    repo_exporter = RestRepositoryExporter(rest_client)
    app_config = cast(GithubPortAppConfig, event.port_app_config)

    pattern_builder = FolderPatternMappingBuilder(
        org_exporter=org_exporter,
        repo_exporter=repo_exporter,
        repo_type=app_config.repository_type,
    )
    repo_path_map = await pattern_builder.build(folders)

    async for folder_batch in folder_exporter.get_paginated_resources(repo_path_map):
        if included_files_enricher:
            folder_batch = await included_files_enricher.enrich_batch(folder_batch)
        yield folder_batch


@ocean.on_resync(ObjectKind.FILE)
@_resync_per_authenticator
async def resync_files(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync files based on configuration using the file exporter."""
    logger.info(f"Starting resync for kind: {kind}")

    config = cast(GithubFileResourceConfig, event.resource_config)
    files = [
        file
        for file in config.selector.files
        if can_access_organization(authenticator, file.organization)
    ]
    if not files:
        return

    rest_client = create_github_client(authenticator)
    org_exporter = RestOrganizationExporter(rest_client)
    file_exporter = RestFileExporter(rest_client)
    repo_exporter = RestRepositoryExporter(rest_client)
    app_config = cast(GithubPortAppConfig, event.port_app_config)
    should_enrich_with_included_files = bool(config.selector.included_files)
    included_files_enricher = (
        IncludedFilesEnricher(
            client=rest_client,
            strategy=FileIncludedFilesStrategy(
                included_files=config.selector.included_files,
            ),
        )
        if should_enrich_with_included_files
        else None
    )

    pattern_builder = FilePatternMappingBuilder(
        org_exporter=org_exporter,
        repo_exporter=repo_exporter,
        repo_type=app_config.repository_type,
    )
    repo_path_map = await pattern_builder.build(files)

    async for file_results in file_exporter.get_paginated_resources(repo_path_map):
        if included_files_enricher:
            file_results = await included_files_enricher.enrich_batch(file_results)
        yield file_results


@ocean.on_resync(ObjectKind.COLLABORATOR)
@_resync_per_authenticator
async def resync_collaborators(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all collaborators in the organization's repositories."""

    rest_client = create_github_client(authenticator)
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    collaborator_exporter = RestCollaboratorExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    config = cast(GithubCollaboratorConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources():
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name,
                organization_type=org["type"],
                type=port_app_config.repository_type,
                search_params=config.selector.repo_search,
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                tasks = []
                for repo in repositories:
                    tasks.append(
                        collaborator_exporter.get_paginated_resources(
                            ListCollaboratorOptions(
                                organization=org_name,
                                repo_name=repo["name"],
                                affiliation=config.selector.affiliation,
                            )
                        )
                    )

                async for collaborators in stream_async_iterators_tasks(*tasks):
                    yield collaborators


@ocean.on_resync(ObjectKind.SECRET_SCANNING_ALERT)
@_resync_per_authenticator
async def resync_secret_scanning_alerts(
    kind: str, authenticator: AbstractGitHubAuthenticator
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync all secret scanning alerts in the organization's repositories."""

    rest_client = create_github_client(authenticator)
    org_exporter = RestOrganizationExporter(rest_client)
    repository_exporter = RestRepositoryExporter(rest_client)
    secret_scanning_alert_exporter = RestSecretScanningAlertExporter(rest_client)

    port_app_config = cast(GithubPortAppConfig, event.port_app_config)
    config = cast(GithubSecretScanningAlertConfig, event.resource_config)

    async for organizations in org_exporter.get_paginated_resources():
        for org in organizations:
            org_name = org["login"]
            repo_options = ListRepositoryOptions(
                organization=org_name,
                organization_type=org["type"],
                type=port_app_config.repository_type,
                search_params=config.selector.repo_search,
            )

            async for repositories in repository_exporter.get_paginated_resources(
                repo_options
            ):
                tasks = []
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
