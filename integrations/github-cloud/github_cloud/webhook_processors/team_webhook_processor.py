from loguru import logger
from github_cloud.helpers.constants import TEAM_DELETE_EVENTS, TEAM_UPSERT_EVENTS
from github_cloud.helpers.utils import ObjectKind
from initialize_client import init_client
from github_cloud.webhook_processors.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

class TeamWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("action")
        event_name = event.headers.get("x-github-event")

        return (
            event_name == "team" and event_type in TEAM_UPSERT_EVENTS + TEAM_DELETE_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.TEAM]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload.get("action")
        team = payload.get("team", {})
        team_name = team.get("name")

        logger.info(f"Processing team event: {action} for team {team_name}")

        if action in TEAM_DELETE_EVENTS:
            logger.info(f"Team {team_name} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[team],
            )

        if not team_name:
            logger.info("Team name is missing, skipping API call")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        client = init_client()
        latest_team = await client.get_single_resource(ObjectKind.TEAM, team_name)

        logger.info(f"Successfully retrieved recent data for team {team_name}")

        if latest_team is None:
            logger.info(f"No data found for team {team_name}")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        return WebhookEventRawResults(updated_raw_results=[latest_team], deleted_raw_results=[])
