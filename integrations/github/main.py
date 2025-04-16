from loguru import logger
from port_ocean.context.ocean import ocean
from initialize_client import create_github_client
from kinds import Kinds
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.team_webhook_processor import TeamWebhookProcessor
from webhook_processors.workflow_webhook_processor import WorkflowRunWebhookProcessor
from webhook_processors.repository_webhook_processor import RepositoryWebhookProcessor


@ocean.on_resync(Kinds.REPOSITORY)
async def on_resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()
    async for repo in client.get_organization_repos():
        yield repo


@ocean.on_resync(Kinds.PULL_REQUEST)
async def on_resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()
    org = client.org
    async for repo in client.get_organization_repos():
        for single_repo in repo:
            repo_name = single_repo.get("name")
            if not repo_name:
                continue
            async for pr in client.get_pull_requests(owner=org, repo=repo_name):
                yield pr


@ocean.on_resync(Kinds.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()
    org = client.org
    async for repo in client.get_organization_repos():
        for single_repo in repo:
            repo_name = single_repo.get("name")
            if not repo_name:
                continue
            async for issue in client.get_issues(owner=org, repo=repo_name):
                if "pull_request" in issue:
                    continue
                yield issue


@ocean.on_resync(Kinds.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()
    async for team in client.get_teams():
        yield team


@ocean.on_resync(Kinds.WORKFLOW)
async def on_resync_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_github_client()
    org = client.org
    async for repo in client.get_organization_repos():
        for single_repo in repo:
            repo_name = single_repo.get("name")
            if not repo_name:
                continue
            async for workflow in client.get_workflows(owner=org, repo=repo_name):
                yield workflow


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting GitHub integration")


@ocean.router.get("/health")
def health():
    return {"status": "ok"}


ocean.add_webhook_processor("/webhook", PullRequestWebhookProcessor)
ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
ocean.add_webhook_processor("/webhook", TeamWebhookProcessor)
ocean.add_webhook_processor("/webhook", WorkflowRunWebhookProcessor)
ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
