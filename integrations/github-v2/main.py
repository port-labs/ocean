from typing import cast

# Load environment configuration before anything else
try:
    from github.config.env_loader import setup_environment

    setup_environment()
except Exception as e:
    from loguru import logger

    logger.warning(f"Failed to load environment configuration: {e}")
    logger.info("Falling back to manual environment variable setup")

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from github.clients.client_factory import create_github_client
from github.helpers.utils import ObjectKind
from github.webhook.webhook_factory.github_webhook_factory import GitHubWebhookFactory
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
from github.webhook.webhook_processors.team_webhook_processor import (
    TeamWebhookProcessor,
)
from integration import (
    RepositoryResourceConfig,
    PullRequestResourceConfig,
    IssueResourceConfig,
    TeamResourceConfig,
)


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean GitHub v1 Integration")
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    # Initialize client
    client = create_github_client()

    # Set up webhooks for live events
    if base_url := ocean.app.base_url:
        logger.info(f"Setting up GitHub webhooks at {base_url}")
        webhook_factory = GitHubWebhookFactory(client, base_url)

        # Create webhooks for repositories and organizations
        # Note: This requires appropriate permissions
        await webhook_factory.create_webhooks_for_all_repositories()
        await webhook_factory.create_organization_webhooks()

        logger.info("GitHub webhook setup completed")
    else:
        logger.warning("No base URL provided, skipping webhook setup")

    logger.info("GitHub integration started successfully")


@ocean.on_resync(ObjectKind.REPOSITORY)
async def on_resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()

    selector = cast(RepositoryResourceConfig, event.resource_config).selector
    include_archived = bool(selector.include_archived)

    params = {}
    if not include_archived:
        params["archived"] = "false"

    batch_count = 0
    async for repos_batch in client.get_repositories(params=params):
        batch_count += 1
        logger.info(
            f"Received repository batch {batch_count} with {len(repos_batch)} repositories"
        )

        yield repos_batch


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def on_resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()

    selector = cast(PullRequestResourceConfig, event.resource_config).selector
    state = selector.state

    async for repos_batch in client.get_repositories():
        logger.info(
            f"Processing batch of {len(repos_batch)} repositories for pull requests"
        )
        params = {"state": state}
        async for pulls_batch in client.get_repositories_resource(
            repos_batch, "pulls", params=params
        ):
            yield pulls_batch


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()

    selector = cast(IssueResourceConfig, event.resource_config).selector
    state = selector.state

    async for repos_batch in client.get_repositories():
        logger.info(f"Processing batch of {len(repos_batch)} repositories for issues")
        params = {"state": state}
        async for issues_batch in client.get_repositories_resource(
            repos_batch, "issues", params=params
        ):
            # Filter out pull requests (GitHub API includes PRs in issues endpoint)
            filtered_batch = [
                issue for issue in issues_batch if "pull_request" not in issue
            ]
            if filtered_batch:
                yield filtered_batch


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()

    selector = cast(TeamResourceConfig, event.resource_config).selector
    privacy = selector.privacy

    async for orgs_batch in client.get_organizations():
        logger.info(f"Processing batch of {len(orgs_batch)} organizations for teams")
        params = {}
        if privacy != "all":
            params["privacy"] = privacy
        async for teams_batch in client.get_organizations_resource(
            orgs_batch, "teams", params=params
        ):
            yield teams_batch


@ocean.on_resync(ObjectKind.WORKFLOW)
async def on_resync_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()

    async for repos_batch in client.get_repositories():
        logger.info(
            f"Processing batch of {len(repos_batch)} repositories for workflows"
        )
        async for workflows_batch in client.get_repositories_resource(
            repos_batch, "actions/workflows"
        ):
            # GitHub returns workflows in a 'workflows' key
            if workflows_batch and isinstance(workflows_batch[0], dict):
                workflows = []
                for workflow_response in workflows_batch:
                    if "workflows" in workflow_response:
                        workflows.extend(workflow_response["workflows"])
                if workflows:
                    yield workflows


# Register webhook processors for live events
ocean.add_webhook_processor("/hook", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/hook", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/hook", IssueWebhookProcessor)
ocean.add_webhook_processor("/hook", WorkflowWebhookProcessor)
ocean.add_webhook_processor("/hook", TeamWebhookProcessor)
