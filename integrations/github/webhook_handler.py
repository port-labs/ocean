from loguru import logger
from fastapi import Request

class WebhookHandler:
    async def handle(self, request: Request) -> dict:
        try:
            payload = await request.json()
            event = request.headers.get("x-github-event")

            logger.info(f"GitHub event: {event}")

            if event == "issues":
                action = payload.get("action")
                issue = payload.get("issue", {}).get("title")
                logger.info(f"Issue {action}: {issue}")

            elif event == "push":
                repo = payload.get("repository", {}).get("full_name")
                logger.info(f"Push to: {repo}")

            elif event == "pull_request":
                pr = payload.get("pull_request", {}).get("title")
                logger.info(f"PR: {pr}")

            else:
                logger.warning(f"Unknown event type: {event}")

            return {"ok": True}
        except Exception as e:
            logger.exception("Webhook handling failed")
            return {"ok": False, "error": str(e)}
