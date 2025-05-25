from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
import asyncio

from github.clients.client_factory import create_github_client
from github.helpers.utils import ObjectKind
from integration import (
    RepositoryResourceConfig,
    GitHubTeamWithMembersResourceConfig,
    GitHubMemberResourceConfig,
    GitHubPullRequestResourceConfig,
    GitHubWorkflowResourceConfig,
    GitHubIssueResourceConfig,
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

from github.webhook.webhook_processors.placeholder_webhook_processor import (
    PlaceholderWebhookProcessor,
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

        org_webhook_factory = OrganizationWebhookFactory(client, base_url)
        await org_webhook_factory.create_webhooks_for_organizations()

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

    async for repos_batch in client.get_repositories():
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

            for issue in issues_batch:
                for repo in repos_batch:
                    if issue.get("repository_url", "").endswith(f"/{repo.get('full_name', '')}"):
                        issue["repository"] = repo
                        break

            if issues_batch:
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
        params = {"state": "open"}

        async for prs_batch in client.get_repository_resource(
            repos_batch, "pulls", params=params
        ):

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

    orgs = []
    async for orgs_batch in client.get_organizations():
        orgs.extend(orgs_batch)

    for org in orgs:
        org_login = org["login"]
        teams = []

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

    orgs = []
    async for orgs_batch in client.get_organizations():
        orgs.extend(orgs_batch)

    for org in orgs:
        org_login = org["login"]
        teams = []


        async for teams_batch in client.rest.get_paginated_org_resource(
            org_login, "teams"
        ):
            teams.extend(teams_batch)

        for i in range(0, len(teams), RESYNC_TEAM_MEMBERS_BATCH_SIZE):
            current_batch = teams[i:i + RESYNC_TEAM_MEMBERS_BATCH_SIZE]

            for team in current_batch:
                async for members_batch in client.get_team_members(
                    org_login, team["slug"]
                ):
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
        logger.info(f"Processing batch of {len(repos_batch)} repositories for workflows")

        async for workflows_batch in client.get_repository_resource(
            repos_batch, "actions/workflows", params=params
        ):
            for workflow in workflows_batch:
                for repo in repos_batch:
                    if workflow.get("repository", {}).get("full_name") == repo.get("full_name"):
                        workflow["repository"] = repo
                        break

            yield workflows_batch


@ocean.on_resync()
async def debug_handler(kind: str):
    logger.info(f"Port requested sync for kind: {kind}")
    yield []


ocean.add_webhook_processor("/hook/org/{org_name}", OrganizationWebhookProcessor)
ocean.add_webhook_processor("/hook/{owner}/{repo}", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/hook/{owner}/{repo}", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/hook/{owner}/{repo}", IssueWebhookProcessor)

ocean.add_webhook_processor("/hook/org/{org_name}", PlaceholderWebhookProcessor)
ocean.add_webhook_processor("/hook/{owner}/{repo}", PlaceholderWebhookProcessor)
