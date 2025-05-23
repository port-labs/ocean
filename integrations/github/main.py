from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
import asyncio

from github.clients.client_factory import create_github_client
from github.helpers.utils import ObjectKind
from intergration import (
    RepositoryResourceConfig,
    GitHubTeamWithMembersResourceConfig,
    GitHubMemberResourceConfig,
    GitHubPullRequestResourceConfig,
)

from github.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from github.webhook.webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from github.webhook.webhook_processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)
from github.webhook.webhook_processors.workflow_webhook_processor import (
    WorkflowWebhookProcessor,
)

from github.webhook.webhook_processors.organization_webhook_processor import (
    OrganizationWebhookProcessor,
)

from github.webhook.webhook_factory.repository_webhook_factory import (
    RepositoryWebhookFactory,
)
from github.webhook.webhook_factory.organization_webhook_factory import (
    OrganizationWebhookFactory,
)


RESYNC_TEAM_MEMBERS_BATCH_SIZE = 10


@ocean.on_start()
async def on_start() -> None:
    """
    Initialize the integration on startup.

    Creates webhooks for organizations and repositories.
    """
    logger.info("Starting Port Ocean GitHub Integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    if base_url := ocean.app.base_url:
        logger.info(f"Creating webhooks using base URL: {base_url}")
        client = create_github_client()

        #Create organization webhooks
        org_webhook_factory = OrganizationWebhookFactory(client, base_url)
        await org_webhook_factory.create_webhooks_for_organizations()

        # Create repository webhooks
        repos = []
        async for repos_batch in client.get_repositories():
            repos.extend(repos_batch)

        repo_webhook_factory = RepositoryWebhookFactory(client, base_url)
        await repo_webhook_factory.create_webhooks_for_repositories(repos)


@ocean.on_resync(ObjectKind.REPOSITORY)
async def on_resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync GitHub repositories.

    Args:
        kind: Entity kind

    Yields:
        Batches of repositories
    """
    client = create_github_client()

    # Default value for include_languages
    include_languages = False

    # Safely get the include_languages attribute if it exists
    try:
        selector = event.resource_config.selector
        if hasattr(selector, 'include_languages'):
            include_languages = bool(selector.include_languages)
    except (AttributeError, TypeError):
        # Handle case where selector might not exist or be of unexpected type
        logger.warning("Could not access include_languages attribute, using default value (False)")

    logger.info(f"Syncing repositories with include_languages={include_languages}")
    async for repos_batch in client.get_repositories(
        include_languages=include_languages
    ):
        logger.info(f"Received repository batch with {len(repos_batch)} repositories")
        yield repos_batch

@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync GitHub issues.

    Args:
        kind: Entity kind

    Yields:
        Batches of issues
    """
    client = create_github_client()
    selector = cast(GitHubIssueResourceConfig, event.resource_config).selector


    params = {
        "per_page": 100
    }
    async for repos_batch in client.get_repositories():
        logger.info(f"Processing batch of {len(repos_batch)} repositories for issues")

        async for issues_batch in client.get_repository_resource(
            repos_batch, "issues", params=params
        ):

            # Enrich issues with repository information
            for issue in issues_batch:
                for repo in repos_batch:
                    if issue.get("repository_url", "").endswith(f"/{repo.get('full_name', '')}"):
                        issue["repository"] = repo
                        break

            if issues_batch:  # Only yield if we have issues after filtering
                yield issues_batch


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def on_resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync GitHub pull requests.

    Args:
        kind: Entity kind

    Yields:
        Batches of pull requests
    """
    client = create_github_client()

    async for repos_batch in client.get_repositories():
        logger.info(f"Processing batch of {len(repos_batch)} repositories for pull requests")

        # Get open pull requests by default
        params = {"state": "open"}

        async for prs_batch in client.get_repository_resource(
            repos_batch, "pulls", params=params
        ):
            # Enrich pull requests with repository information
            for pr in prs_batch:
                for repo in repos_batch:
                    if pr.get("url", "").startswith(repo.get("url", "") + "/"):
                        pr["repository"] = repo
                        break

            yield prs_batch


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams_with_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync GitHub teams with members.

    Args:
        kind: Entity kind

    Yields:
        Batches of teams with members
    """
    client = create_github_client()
    selector = cast(
        GitHubTeamWithMembersResourceConfig, event.resource_config
    ).selector

    # Get organizations
    orgs = []
    async for orgs_batch in client.get_organizations():
        orgs.extend(orgs_batch)

    # For each organization, get teams
    for org in orgs:
        org_login = org["login"]
        teams = []

        # Get teams for the organization
        async for teams_batch in client.rest.get_paginated_org_resource(
            org_login, "teams"
        ):
            yield teams_batch


@ocean.on_resync(ObjectKind.USER)
async def on_resync_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync GitHub members.

    Args:
        kind: Entity kind

    Yields:
        Batches of members
    """
    client = create_github_client()
    selector = cast(GitHubMemberResourceConfig, event.resource_config).selector

    # Get organizations
    orgs = []
    async for orgs_batch in client.get_organizations():
        orgs.extend(orgs_batch)

    # For each organization, get teams and members
    for org in orgs:
        org_login = org["login"]
        teams = []

        # Get teams for the organization
        async for teams_batch in client.rest.get_paginated_org_resource(
            org_login, "teams"
        ):
            teams.extend(teams_batch)

        # Process teams in batches
        for i in range(0, len(teams), RESYNC_TEAM_MEMBERS_BATCH_SIZE):
            current_batch = teams[i:i + RESYNC_TEAM_MEMBERS_BATCH_SIZE]

            # For each team, get members
            for team in current_batch:
                async for members_batch in client.get_team_members(
                    org_login, team["slug"]
                ):
                    # Add team and organization context to each member
                    for member in members_batch:
                        member["team"] = team

                    yield members_batch



@ocean.on_resync(ObjectKind.WORKFLOW)
async def on_resync_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """
    Resync GitHub workflow runs.

    Args:
        kind: Entity kind

    Yields:
        Batches of workflow runs
    """
    client = create_github_client()
    selector = cast(GitHubWorkflowResourceConfig, event.resource_config).selector


    params = {
        "per_page": 100
    }


    async for repos_batch in client.get_repositories():
        logger.info(f"Processing batch of {len(repos_batch)} repositories for workflow runs")

        async for workflows_batch in client.get_repository_resource(
            repos_batch, "actions/runs", params=params
        ):
            # Enrich workflow runs with repository information
            for workflow in workflows_batch:
                for repo in repos_batch:
                    if workflow.get("repository", {}).get("full_name") == repo.get("full_name"):
                        workflow["repository"] = repo
                        break

            yield workflows_batch


@ocean.on_resync()  # Catch-all handler
async def debug_handler(kind: str):
    logger.info(f"Port requested sync for kind: {kind}")
    yield []


# Register webhook processors
ocean.add_webhook_processor("/hook/org/{org_name}", OrganizationWebhookProcessor)
ocean.add_webhook_processor("/hook/{owner}/{repo}", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/hook/{owner}/{repo}", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/hook/{owner}/{repo}", IssueWebhookProcessor)
ocean.add_webhook_processor("/hook/{owner}/{repo}", WorkflowWebhookProcessor)
