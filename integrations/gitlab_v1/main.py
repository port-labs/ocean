from typing import AsyncGenerator, Dict, Any
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from fastapi import Request
from loguru import logger
from gitlab_integration import GitLabIntegration, ObjectKind


gitlab_integration = GitLabIntegration()


@ocean.router.post("/webhook/gitlab")
async def gitlab_webhook(request: Request):
    payload = await request.json()
    event_type = payload.get("object_kind")


    await gitlab_integration.handle_webhook_event(event_type, payload)
    return {"status": "success"}


@ocean.on_resync(ObjectKind.GROUP)
async def on_resync_groups(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for item in gitlab_integration.resync_resources(ObjectKind.GROUP):
        yield item


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for item in gitlab_integration.resync_resources(ObjectKind.PROJECT):
        yield item


@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def on_resync_merge_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for item in gitlab_integration.resync_resources(ObjectKind.MERGE_REQUEST):
        yield item


@ocean.on_resync(ObjectKind.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for item in gitlab_integration.resync_resources(ObjectKind.ISSUE):
        yield item


@ocean.on_start()
async def on_start() -> None:
    try:
        await gitlab_integration.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize GitLab integration: {str(e)}")

