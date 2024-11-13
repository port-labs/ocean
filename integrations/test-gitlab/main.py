from fastapi import Request
from loguru import logger
from port_ocean.context.ocean import ocean

from client import GitLabHandler, KindNotImplementedException

logger.remove()
logger.add(lambda msg: print(msg, end=""), colorize=True, level="INFO")

@ocean.router.post("/webhook")
async def gitlab_webhook(request: Request) -> dict[str, bool]:
    try:
        payload = await request.json()

        logger.info(
            f"Received payload: {payload} and headers {request.headers} from gitlab"
        )

        webhook_secret = ocean.integration_config.get("gitlab_secret")
        secret_key = request.headers.get("X-Gitlab-Token")
        if not secret_key or secret_key != webhook_secret:
            return {"success": False}

        handler = GitLabHandler()

        event = request.headers.get("X-Gitlab-Event")
        if event == "System Hook":
            await handler.system_hook_handler(payload)
        else:
            await handler.webhook_handler(payload)

        logger.info("Webhook processed successfully.")
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")

    return {"success": True}

@ocean.on_resync("group")
async def resync_group(kind: str) -> list[dict]:
    handler = GitLabHandler()
    results = []
    async for page in handler.fetch_data("/groups"):
        results.extend(page)
    return results

@ocean.on_resync("project")
async def resync_project(kind: str) -> list[dict]:
    handler = GitLabHandler()
    results = []
    async for page in handler.fetch_data("/projects?membership=yes"):
        results.extend(page)
    return results

@ocean.on_resync("merge_request")
async def resync_merge_request(kind: str) -> list[dict]:
    handler = GitLabHandler()
    results = []
    async for page in handler.fetch_data("/merge_requests"):
        results.extend(page)
    return results

@ocean.on_resync("issue")
async def resync_issues(kind: str) -> list[dict]:
    handler = GitLabHandler()
    results = []
    async for page in handler.fetch_data("/issues"):
        results.extend(page)
    return results

@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting gitlab integration")