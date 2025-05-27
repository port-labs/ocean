import asyncio

from loguru import logger

from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


from github.clients.client_factory import create_github_client
from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from github.webhook.webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from github.webhook.webhook_processors.issue_webhook_processor import (
    IssueWebhookProcessor,
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
    client = create_github_client()
    async for repos_batch in client.get_repositories():
        yield repos_batch

@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()

    async for repos_batch in client.get_repositories():
        logger.info(f"Processing batch of {len(repos_batch)} repositories for issues")
        async for issues in client.get_repository_resource(repos_batch, "issues"):
            yield issues

@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def on_resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()
    async for repos_batch in client.get_repositories():
        logger.info(f"Processing batch of {len(repos_batch)} repositories for pull requests")
        async for pulls in client.get_repository_resource(repos_batch, "pulls"):
            yield pulls

@ocean.on_resync(ObjectKind.WORKFLOW)
async def on_resync_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()
    async for repos_batch in client.get_repositories():
        logger.info(f"Processing batch of {len(repos_batch)} repositories for workflows")
        async for workflows in client.get_repository_resource(repos_batch, "actions/workflows"):
            yield workflows

@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams_with_members(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()
    async for orgs_batch in client.get_organizations():
        async for teams in client.get_organization_resource(orgs_batch, "teams"):
            yield teams



ocean.add_webhook_processor("/hook/org/{org_name}", OrganizationWebhookProcessor)
ocean.add_webhook_processor("/hook/{owner}/{repo}", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/hook/{owner}/{repo}", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/hook/{owner}/{repo}", IssueWebhookProcessor)
