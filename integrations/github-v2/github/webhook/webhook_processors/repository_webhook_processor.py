from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from github.webhook.webhook_processors._github_abstract_webhook_processor import (
    _GitHubAbstractWebhookProcessor,
)


class RepositoryWebhookProcessor(_GitHubAbstractWebhookProcessor):
    events = [
        "created",
        "deleted",
        "archived",
        "unarchived",
        "publicized",
        "privatized",
    ]
    hooks = ["repository"]

    async def _process_webhook_event(self, event: WebhookEvent) -> None:
        repository_data = event.payload.get("repository", {})
        action = event.payload.get("action")

        logger.info(
            f"Processing repository {action} event for {repository_data.get('full_name')}"
        )

        if action in ["deleted", "archived"]:
            # Handle repository deletion/archiving
            await ocean.unregister_raw(
                "repository", [{"id": str(repository_data.get("id"))}]
            )
        else:
            # Handle repository creation/updates
            await ocean.register_raw("repository", [repository_data])
