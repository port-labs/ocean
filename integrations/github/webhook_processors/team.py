from loguru import logger
from client import GitHubClient
from consts import TEAM_DELETE_EVENTS, TEAM_UPSERT_EVENTS
from helpers.utils import ObjectKind
from webhook_processors.abstract import GitHubAbstractWebhookProcessor
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

class TeamWebhookProcessor(GitHubAbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.payload.get("action") in TEAM_UPSERT_EVENTS
            or event.payload.get("action") in TEAM_DELETE_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.TEAM]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        client = GitHubClient.from_ocean_config()
        team = payload.get("team", {})
        
        if payload.get("action") in TEAM_DELETE_EVENTS:
            logger.info(f"Team {team.get('name')} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[team],
            )

        logger.info(f"Got event for team {team.get('name')}: {payload.get('action')}")
        return WebhookEventRawResults(
            updated_raw_results=[team],
            deleted_raw_results=[],
        ) 