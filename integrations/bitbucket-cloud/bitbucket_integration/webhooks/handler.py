from loguru import logger
from bitbucket_integration.utils import validate_webhook_payload
from bitbucket_integration.models.main import ObjectKind
from starlette.requests import Request
from port_ocean.context.ocean import ocean


class BitbucketWebhookHandler:
    def __init__(self):
        self.secret = ocean.integration_config.get("webhook_secret")
        self.event_handlers = {
            "repo:push": self.process_repo_push_event,
            "pullrequest:created": self.process_pull_request_created_event,
            "pullrequest:updated": self.process_pull_request_updated_event,
        }

    async def handle_webhook(self, request: Request) -> dict:
        """Handle incoming webhook events from Bitbucket."""
        if not await validate_webhook_payload(request, self.secret):
            return {"ok": False, "error": "Unauthorized"}

        event = await request.json()
        event_type = request.headers.get("X-Event-Key")
        logger.info(f"Received Bitbucket webhook event: {event_type}")

        try:
            handler = self.event_handlers.get(event_type)
            if handler:
                await handler(event)
            else:
                logger.warning(f"No handler found for event type: {event_type}")
                return {"ok": False, "error": f"Unsupported event type: {event_type}"}

            return {"ok": True}
        except Exception as e:
            logger.error(f"Failed to handle webhook event: {e}")
            return {"ok": False, "error": str(e)}

    async def process_repo_push_event(self, event: dict) -> None:
        """Process a repo:push event."""
        repo = event["repository"]
        logger.info(f"Processing push event for repository: {repo['name']}")

        await ocean.register_raw(ObjectKind.REPOSITORY, [repo])

    async def process_pull_request_created_event(self, event: dict) -> None:
        """Process a pullrequest:created event."""
        pr = event["pullrequest"]
        repo = event["repository"]
        logger.info(f"Processing created pull request: PR #{pr['id']} - {pr['title']}")

        pr_data = {**pr, "repository": repo}

        await ocean.register_raw(ObjectKind.PULL_REQUEST, [pr_data])

    async def process_pull_request_updated_event(self, event: dict) -> None:
        """Process a pullrequest:updated event."""
        pr = event["pullrequest"]
        repo = event["repository"]
        logger.info(f"Processing updated pull request: PR #{pr['id']} - {pr['title']}")

        pr_data = {**pr, "repository": repo}

        await ocean.register_raw(ObjectKind.PULL_REQUEST, [pr_data])
