from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
import os
from loguru import logger
from utils import ObjectKind
from github_client import GitHubClient
from webhook_handler import WebhookHandler
from fastapi import Request

webhook_handler = WebhookHandler()

client = None
integration_config = None
RESYNC_BATCH_SIZE = 10

@ocean.on_start()
async def on_start():
    global client
    global integration_config
    token = os.getenv("OCEAN__GITHUB_TOKEN")
    client = GitHubClient(token)
    integration_config = ocean.integration_config
    logger.info("GitHub client initialized using Ocean's async HTTP client.")


@ocean.on_resync(ObjectKind.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"[repositories] kind: {kind}")
    
    repos = await client.get_repositories(integration_config["github_org"])
    # Process repositories in batches
    for i in range(0, len(repos), RESYNC_BATCH_SIZE):
        batch = repos[i:i + RESYNC_BATCH_SIZE]
        logger.info(f"Processing repositories batch {i//RESYNC_BATCH_SIZE + 1}, size: {len(batch)}")
        yield [
            {
                "identifier": str(repo["id"]),
                "title": repo["name"],
                "description": repo.get("description"),
                "url": repo.get("html_url")
            }
            for repo in batch
        ]


@ocean.on_resync(ObjectKind.ISSUE)
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    issues = await client.get_issues(integration_config["github_org"], integration_config["github_repo"])
    logger.info(f"Found {len(issues)} issues total")
    
    # Process issues in batches
    for i in range(0, len(issues), RESYNC_BATCH_SIZE):
        batch = issues[i:i + RESYNC_BATCH_SIZE]
        logger.info(f"Processing issues batch {i//RESYNC_BATCH_SIZE + 1}, size: {len(batch)}")
        yield [
            {
                "identifier": str(issue["id"]),
                "title": issue["title"],
                "state": issue["state"],
                "url": issue["html_url"]
            }
            for issue in batch
        ]

@ocean.on_resync(ObjectKind.PULLREQUEST)
async def resync_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    pulls = await client.get_pull_requests(integration_config["github_org"], integration_config["github_repo"])
    logger.info(f"Found {len(pulls)} pull requests total")
    
    # Process pull requests in batches
    for i in range(0, len(pulls), RESYNC_BATCH_SIZE):
        batch = pulls[i:i + RESYNC_BATCH_SIZE]
        logger.info(f"Processing pull requests batch {i//RESYNC_BATCH_SIZE + 1}, size: {len(batch)}")
        yield [
            {
                "identifier": str(pr["id"]),
                "title": pr["title"],
                "state": pr["state"],
                "url": pr["html_url"],
                "author": pr["user"]["login"]
            }
            for pr in batch
        ]

@ocean.on_resync(ObjectKind.WORKFLOW)
async def resync_workflows(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    workflows = await client.get_workflows(integration_config["github_org"], integration_config["github_repo"])
    logger.info(f"Found {len(workflows)} workflows total")
    
    # Process workflows in batches
    for i in range(0, len(workflows), RESYNC_BATCH_SIZE):
        batch = workflows[i:i + RESYNC_BATCH_SIZE]
        logger.info(f"Processing workflows batch {i//RESYNC_BATCH_SIZE + 1}, size: {len(batch)}")
        yield [
            {
                "identifier": str(wf["id"]),
                "name": wf["name"],
                "state": wf["state"],
                "created_at": wf["created_at"],
                "url": wf["html_url"]
            }
            for wf in batch
        ]


@ocean.on_resync(ObjectKind.TEAM)
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    teams = await client.get_teams(integration_config["github_org"])
    logger.info(f"Found {len(teams)} teams total")
    
    # Process teams in batches
    for i in range(0, len(teams), RESYNC_BATCH_SIZE):
        batch = teams[i:i + RESYNC_BATCH_SIZE]
        logger.info(f"Processing teams batch {i//RESYNC_BATCH_SIZE + 1}, size: {len(batch)}")
        yield [
            {
                "identifier": str(team["id"]),
                "name": team["name"],
                "description": team.get("description", ""),
                "slug": team["slug"]
            }
            for team in batch
        ]


@ocean.router.post("/webhook")
async def github_webhook(request: Request):
    return await webhook_handler.handle(request)

