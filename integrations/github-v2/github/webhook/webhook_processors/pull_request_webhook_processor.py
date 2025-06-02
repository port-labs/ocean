from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from github.webhook.webhook_processors._github_abstract_webhook_processor import (
    _GitHubAbstractWebhookProcessor,
)


class PullRequestWebhookProcessor(_GitHubAbstractWebhookProcessor):
    events = [
        "opened",
        "closed",
        "reopened",
        "edited",
        "synchronize",
        "ready_for_review",
        "converted_to_draft",
    ]
    hooks = ["pull_request"]

    async def _process_webhook_event(self, event: WebhookEvent) -> None:
        pull_request_data = event.payload.get("pull_request", {})
        action = event.payload.get("action")

        logger.info(
            f"Processing pull request {action} event for PR #{pull_request_data.get('number')} "
            f"in {event.payload.get('repository', {}).get('full_name')}"
        )

        if action == "closed" and not pull_request_data.get("merged"):
            # Handle PR closure without merge - could optionally unregister
            pass

        # Register/update the pull request
        await ocean.register_raw("pull-request", [pull_request_data])
