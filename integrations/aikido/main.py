from typing import Any, AsyncGenerator
from port_ocean.context.ocean import ocean
from loguru import logger

from initialize_client import init_aikido_client
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.repository_webhook_processor import RepositoryWebhookProcessor
from integration import ObjectKind


@ocean.on_resync(ObjectKind.REPOSITORY)
async def on_repositories_resync(
    kind: str,
) -> AsyncGenerator[list[dict[str, Any]], None]:
    client = init_aikido_client()
    logger.info("Fetching repositories from Aikido API")
    async for repos_batch in client.get_repositories():
        logger.info(f"Yielding repositories batch of size: {len(repos_batch)}")
        yield repos_batch


@ocean.on_resync(ObjectKind.ISSUES)
async def on_issues_resync(kind: str) -> AsyncGenerator[list[dict[str, Any]], None]:
    client = init_aikido_client()
    logger.info("Fetching all issues from Aikido API")
    async for issue_batch in client.get_issues_in_batches():
        logger.info(f"Yielding issues batch of size: {len(issue_batch)}")
        yield issue_batch


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Aikido integration")


ocean.add_webhook_processor("/webhook", RepositoryWebhookProcessor)
ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
