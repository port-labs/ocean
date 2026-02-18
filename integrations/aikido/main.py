from typing import Any, AsyncGenerator
from port_ocean.context.ocean import ocean
from port_ocean.context.event import event
from loguru import logger
from typing import cast

from initialize_client import init_aikido_client
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.repository_webhook_processor import RepositoryWebhookProcessor
from integration import ObjectKind, RepositoryResourceConfig


@ocean.on_resync(ObjectKind.REPOSITORY)
async def on_repositories_resync(
    kind: str,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    client = init_aikido_client()
    selector = cast(RepositoryResourceConfig, event.resource_config).selector
    query_params = {"include_inactive": selector.include_inactive}
    logger.info("Fetching repositories from Aikido API")
    async for repos_batch in client.get_repositories(query_params=query_params):
        logger.info(f"Yielding repositories batch of size: {len(repos_batch)}")
        yield repos_batch


@ocean.on_resync(ObjectKind.ISSUES)
async def on_issues_resync(kind: str) -> AsyncGenerator[list[dict[str, Any]], None]:
    client = init_aikido_client()
    logger.info("Fetching all issues from Aikido API")
    async for issue_batch in client.get_issues_in_batches():
        logger.info(f"Yielding issues batch of size: {len(issue_batch)}")
        yield issue_batch


@ocean.on_resync(ObjectKind.ISSUE_GROUPS)
async def on_issue_groups_resync(
    kind: str,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    client = init_aikido_client()
    logger.info("Fetching open issue groups from Aikido API")
    async for issue_group_batch in client.get_open_issue_groups():
        logger.info(f"Yielding open issue groups batch of size: {len(issue_group_batch)}")
        yield issue_group_batch


@ocean.on_resync(ObjectKind.TEAM)
async def on_teams_resync(kind: str) -> AsyncGenerator[list[dict[str, Any]], None]:
    client = init_aikido_client()
    logger.info("Fetching teams from Aikido API")
    async for team_batch in client.get_teams():
        logger.info(f"Yielding teams batch of size: {len(team_batch)}")
        yield team_batch


@ocean.on_resync(ObjectKind.CONTAINER)
async def on_containers_resync(
    kind: str,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    client = init_aikido_client()
    logger.info("Fetching containers from Aikido API")
    async for container_batch in client.get_containers():
        logger.info(f"Yielding containers batch of size: {len(container_batch)}")
        yield container_batch


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Aikido integration")


ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
