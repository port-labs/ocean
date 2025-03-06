from enum import StrEnum
from loguru import logger
import hmac
import hashlib
from starlette.requests import Request
from port_ocean.context.ocean import ocean

class ObjectKind(StrEnum):
    REPOSITORY = "repository"
    PROJECT = "project"
    PULL_REQUEST = "pull-request"
    COMPONENT = "component"

class BitbucketOceanWebhookHandler:
    def __init__(self):
        # self.secret = ocean.integration_config.get("webhook_secret")
        self.secret = ocean.integration_config["webhook_secret"]
        self.event_handlers = {
            "repo:push": self.process_repo_push_event,
            "pullrequest:created": self.process_pull_request_created_event,
            "pullrequest:updated": self.process_pull_request_updated_event,
        }

    async def handle_webhook(self, request: Request) -> dict:
        if not await check_webhook(request, self.secret):
            logger.warning("Unauthorized webhook attempt detected.")
            return {"ok": False, "error": "Unauthorized"}

        event_type = request.headers.get("X-Event-Key", "unknown")
        event_data = await request.json()

        logger.info(f"Received Bitbucket webhook event: {event_type}")

        handler = self.event_handlers.get(event_type)

        if not handler:
            logger.warning(f"Unsupported event type received: {event_type}")
            return {"ok": False, "error": f"Unsupported event type: {event_type}"}

        try:
            await handler(event_data)
            return {"ok": True}
        except KeyError as e:
            logger.error(f"Missing expected key in event payload: {e}")
            return {"ok": False, "error": f"Malformed payload: {e}"}
        except Exception as e:
            logger.exception(f"Unexpected error processing event '{event_type}': {e}")
            return {"ok": False, "error": str(e)}

    async def process_repo_push_event(self, event: dict) -> None:
        repo = event.get("repository", {})
        repo_name = repo.get("name", "Unknown Repository")
        logger.info(f"Processing push event for repository: {repo_name}")

        await ocean.register_raw(ObjectKind.REPOSITORY, [repo])

    async def process_pull_request_created_event(self, event: dict) -> None:
        pr = event.get("pullrequest", {})
        repo = event.get("repository", {})
        pr_id = pr.get("id", "Unknown PR")
        pr_title = pr.get("title", "Untitled PR")

        logger.info(f"Processing created pull request: PR #{pr_id} - {pr_title}")

        pr_data = {**pr, "repository": repo}
        await ocean.register_raw(ObjectKind.PULL_REQUEST, [pr_data])

    async def process_pull_request_updated_event(self, event: dict) -> None:
        pr = event.get("pullrequest", {})
        repo = event.get("repository", {})
        pr_id = pr.get("id", "Unknown PR")
        pr_title = pr.get("title", "Untitled PR")

        logger.info(f"Processing pull request: PR #{pr_id} - {pr_title}")

        pr_data = {**pr, "repository": repo}
        await ocean.register_raw(ObjectKind.PULL_REQUEST, [pr_data])

async def check_webhook(request: Request, secret: str) -> bool:
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature")
    if not signature:
        logger.error("Missing X-Hub-Signature header")
        return False
    hash_object = hmac.new(secret.encode(), payload, hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(signature, expected_signature)