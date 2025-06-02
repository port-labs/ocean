from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from github.webhook.webhook_processors._github_abstract_webhook_processor import (
    _GitHubAbstractWebhookProcessor,
)


class IssueWebhookProcessor(_GitHubAbstractWebhookProcessor):
    events = [
        "opened",
        "closed",
        "reopened",
        "edited",
        "assigned",
        "unassigned",
        "labeled",
        "unlabeled",
    ]
    hooks = ["issues"]

    async def _process_webhook_event(self, event: WebhookEvent) -> None:
        issue_data = event.payload.get("issue", {})
        action = event.payload.get("action")

        # Skip if this is actually a pull request (GitHub includes PRs in issues)
        if "pull_request" in issue_data:
            logger.debug("Skipping issue webhook for pull request")
            return

        logger.info(
            f"Processing issue {action} event for issue #{issue_data.get('number')} "
            f"in {event.payload.get('repository', {}).get('full_name')}"
        )

        if action == "deleted":
            # Handle issue deletion
            await ocean.unregister_raw("issue", [{"id": str(issue_data.get("id"))}])
        else:
            # Register/update the issue
            await ocean.register_raw("issue", [issue_data])
