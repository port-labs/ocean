from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from github.webhook.webhook_processors._github_abstract_webhook_processor import (
    _GitHubAbstractWebhookProcessor,
)


class TeamWebhookProcessor(_GitHubAbstractWebhookProcessor):
    events = [
        "created",
        "deleted",
        "edited",
        "added_to_repository",
        "removed_from_repository",
    ]
    hooks = ["team"]

    async def _process_webhook_event(self, event: WebhookEvent) -> None:
        team_data = event.payload.get("team", {})
        action = event.payload.get("action")

        logger.info(
            f"Processing team {action} event for team '{team_data.get('name')}' "
            f"in organization {event.payload.get('organization', {}).get('login')}"
        )

        if action == "deleted":
            # Handle team deletion
            await ocean.unregister_raw("team", [{"id": str(team_data.get("id"))}])
        else:
            # Register/update the team
            await ocean.register_raw("team", [team_data])
