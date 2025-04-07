from typing import Any, cast

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from webhook_processors.repository_webhook_processor import RepositoryWebhookProcessor
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from webhook_processors.team_webhook_processor import TeamWebhookProcessor
from webhook_processors.workflow_webhook_processor import WorkflowWebhookProcessor
from utils.initialize_client import get_client

from integration import (
    RepositoryResourceConfig,
    IssueResourceConfig,
    PullRequestResourceConfig,
    TeamResourceConfig,
    WorkflowResourceConfig,
    ObjectKind,
)


@ocean.on_start()
async def on_start() -> None:
    """Handle integration start."""
    logger.info("Starting GitHub Cloud integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    client = get_client()
    logger.info("Subscribing to GitHub webhooks")
    await client.create_webhooks_if_not_exists()


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repository(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync repositories."""
    client = get_client()
    selector = cast(RepositoryResourceConfig, event.resource_config).selector

    if not selector.organizations:
        organizations_str = ocean.integration_config.get("githubOrganization")
        selector.organizations = client._parse_organizations(organizations_str)

    logger.info(f"Resyncing repositories for organizations: {selector.organizations}")
    async for repos in client.get_repositories(selector.organizations):
        logger.info(f"Fetching repositories with batch size: {len(repos)}")
        yield repos


@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync issues."""
    client = get_client()
    selector = cast(IssueResourceConfig, event.resource_config).selector

    if not selector.organizations:
        organizations_str = ocean.integration_config.get("githubOrganization")
        selector.organizations = client._parse_organizations(organizations_str)

    logger.info(f"Resyncing issues for organizations: {selector.organizations}")
    async for issues in client.get_issues(selector.organizations, selector.state):
        logger.info(f"Fetching issues with batch size: {len(issues)}")
        yield issues


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync pull requests."""
    client = get_client()
    selector = cast(PullRequestResourceConfig, event.resource_config).selector

    if not selector.organizations:
        organizations_str = ocean.integration_config.get("githubOrganization")
        selector.organizations = client._parse_organizations(organizations_str)

    logger.info(f"Resyncing pull requests for organizations: {selector.organizations}")
    async for pull_requests in client.get_pull_requests(
        selector.organizations, selector.state
    ):
        logger.info(f"Fetching pull requests with batch size: {len(pull_requests)}")
        yield pull_requests


@ocean.on_resync(ObjectKind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync teams."""
    client = get_client()
    selector = cast(TeamResourceConfig, event.resource_config).selector

    if not selector.organizations:
        organizations_str = ocean.integration_config.get("githubOrganization")
        selector.organizations = client._parse_organizations(organizations_str)

    logger.info(f"Resyncing teams for organizations: {selector.organizations}")
    async for teams in client.get_teams(selector.organizations):
        logger.info(f"Fetching teams with batch size: {len(teams)}")
        yield teams


@ocean.on_resync(ObjectKind.WORKFLOW)
async def resync_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Resync workflows."""
    client = get_client()
    selector = cast(WorkflowResourceConfig, event.resource_config).selector

    if not selector.organizations:
        organizations_str = ocean.integration_config.get("githubOrganization")
        selector.organizations = client._parse_organizations(organizations_str)

    logger.info(f"Resyncing workflows for organizations: {selector.organizations}")

    all_workflows = []
    async for workflows in client.get_workflows(selector.organizations):
        logger.info(f"Fetching workflows with batch size: {len(workflows)}")
        if workflows.get("total_count", 0) > 0 or workflows.get("workflows"):
            all_workflows.append(workflows)
        yield workflows

    flattened_workflows = [
        workflow
        for workflow_group in all_workflows
        for workflow in workflow_group.get("workflows", [])
    ]

    for workflow in flattened_workflows:
        if "id" in workflow:
            workflow_id = workflow["id"]
            logger.info(f"Fetching workflow runs for workflow ID: {workflow_id}")
            async for workflow_runs in client.get_workflow_runs(
                selector.organizations, workflow_id
            ):
                if workflow_runs:
                    workflow["runs"] = workflow_runs
                    logger.info(
                        f"Added {len(workflow_runs)} runs to workflow {workflow_id}"
                    )
                    yield [workflow]


webhook_processors = [
    RepositoryWebhookProcessor,
    IssueWebhookProcessor,
    PullRequestWebhookProcessor,
    TeamWebhookProcessor,
    WorkflowWebhookProcessor,
]

for processor in webhook_processors:
    ocean.add_webhook_processor("/webhook", processor)
