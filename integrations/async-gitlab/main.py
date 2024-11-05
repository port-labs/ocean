from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from gitlab_core.client import GitLabClient
from gitlab_core.helpers.utils import ObjectKind

@ocean.on_resync()
async def on_resources_resync(kind: str) -> None:
    logger.info(f"Received re-sync for kind {kind}")
    return

@ocean.on_resync(ObjectKind.GROUP)
async def on_group_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Group Re-sync req received")
    gitlab_client = GitLabClient.create_from_ocean_config()

    async for groups in gitlab_client.get_groups():
        logger.info(f"Re-syncing {len(groups)} groups")
        yield groups
        return

@ocean.on_resync(ObjectKind.PROJECT)
async def on_project_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Project Re-sync req received")
    gitlab_client = GitLabClient.create_from_ocean_config()

    async for projects in gitlab_client.get_projects():
        logger.info(f"Re-syncing {len(projects)} projects")
        yield projects
        return

@ocean.on_resync(ObjectKind.MERGE_REQUEST)
async def on_merge_request_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    gitlab_client = GitLabClient.create_from_ocean_config()

    async for merge_requests in gitlab_client.get_merge_requests():
        logger.info(f"Re-syncing {len(merge_requests)} merge requests")
        yield merge_requests
        return

@ocean.on_resync(ObjectKind.ISSUE)
async def on_issue_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    gitlab_client = GitLabClient.create_from_ocean_config()

    async for issues in gitlab_client.get_issues():
        logger.info(f"Re-syncing {len(issues)} issues")
        yield issues
        return

# @ocean.router.post("/webhook")
# async def on_webhook_alert(request: Request) -> dict[str, Any]:
#     body = await request.json()
#     webhook_event = WebhookEvent(
#         eventType=body.get("eventType"), publisherId=body.get("publisherId")
#     )
#     await webhook_event_handler.notify(webhook_event, body)
#     return {"ok": True}
#
# # Optional
# # Listen to the start event of the integration. Called once when the integration starts.
# @ocean.on_start()
# async def on_start() -> None:
#     # Something to do when the integration starts
#     # For example create a client to query 3rd party services - GitHub, Jira, etc...
#     print("Starting async-gitlab integration")
