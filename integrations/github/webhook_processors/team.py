from loguru import logger
from consts import TEAM_DELETE_EVENTS, TEAM_UPSERT_EVENTS
from helpers.utils import ObjectKind
from client import GitHubClient
from webhook_processors.abstract import GitHubAbstractWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class TeamWebhookProcessor(GitHubAbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("action")
        event = event.headers.get("x-github-event")

        return event == "team" and event_type in TEAM_UPSERT_EVENTS + TEAM_DELETE_EVENTS

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.TEAM]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle team webhook events."""
        action = payload.get("action")
        team = payload.get("team", {})
        team_slug = team.get("slug")

        logger.info(f"Processing team event: {action} for team {team_slug}")

        if action in TEAM_DELETE_EVENTS:
            logger.info(f"Team {team.get('name')} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[team],
            )

        client = GitHubClient.from_ocean_config()
        latest_team = await client.get_single_resource(ObjectKind.TEAM, team_slug)

        return WebhookEventRawResults(
            updated_raw_results=[latest_team], deleted_raw_results=[]
        )
