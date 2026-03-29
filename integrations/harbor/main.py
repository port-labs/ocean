from fastapi import Request
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.client import HarborClient
from core.webhook_handler import validate_webhook_secret, process_webhook_event
from utils.types import HarborResourceType


def init_client() -> HarborClient:
    return HarborClient(
        base_url=ocean.integration_config["harbor_url"],
        username=ocean.integration_config["harbor_username"],
        password=ocean.integration_config["harbor_password"],
    )


@ocean.on_resync(HarborResourceType.PROJECT)
async def resync_project(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    logger.info("Resyncing projects for Harbor integration")
    async for projects in client.get_projects():
        yield projects


@ocean.on_resync(HarborResourceType.USER)
async def resync_user(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    logger.info("Resyncing users for Harbor integration")
    async for users in client.get_users():
        yield users


@ocean.on_resync(HarborResourceType.REPOSITORY)
async def resync_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    async for projects in client.get_projects():
        logger.info(
            f"Resyncing repositories for {len(projects)} projects for repositories"
        )
        for project in projects:
            async for repos in client.get_repositories(project["name"]):
                yield repos


@ocean.on_resync(HarborResourceType.ARTIFACT)
async def resync_artifact(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = init_client()
    async for projects in client.get_projects():
        logger.info(f"Resyncing artifacts for {len(projects)} projects for artifacts")
        for project in projects:
            async for repos in client.get_repositories(project["name"]):
                for repo in repos:
                    repo_name = repo["name"].split("/", 1)[1]
                    async for artifacts in client.get_artifacts(
                        project["name"], repo_name
                    ):
                        yield artifacts


@ocean.router.post("/webhook")
async def handle_webhook(request: Request) -> dict:
    if not await validate_webhook_secret(request):
        logger.warning("Webhook request failed secret validation")
        return {"ok": False, "error": "Invalid webhook secret"}

    payload = await request.json()
    logger.info(f"Received webhook event: {payload.get('type', 'unknown')}")

    client = init_client()
    await process_webhook_event(payload, client)

    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Harbor integration")
