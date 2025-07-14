from typing import cast
from loguru import logger
from github.core.exporters.team_exporter import (
    GraphQLTeamWithMembersExporter,
)
from github.core.options import SingleTeamOptions
from github.webhook.events import (
    MEMBERSHIP_DELETE_EVENTS,
    TEAM_MEMBERSHIP_EVENTS,
)
from github.helpers.utils import GithubClientType, ObjectKind
from github.clients.client_factory import create_github_client
from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from integration import GithubTeamConfig


class TeamMemberWebhookProcessor(_GithubAbstractWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        if not event.payload.get("action"):
            return False

        if event.payload["action"] not in (TEAM_MEMBERSHIP_EVENTS):
            return False

        event_name = event.headers.get("x-github-event")
        return event_name == "membership"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.TEAM]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        team = payload["team"]
        member = payload["member"]

        logger.info(f"Processing {action} event for team {team['name']}")

        config = cast(GithubTeamConfig, resource_config)
        selector = config.selector

        if not selector.members:
            logger.info("Member selector disabled, skipping ...")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        if action in MEMBERSHIP_DELETE_EVENTS:
            logger.info(
                f"Member '{member['login']}' was removed from team '{team['name']}'. "
                f"Explicit deletion will be skipped as the user might still be a member of other teams. "
            )

        if not team.get("slug"):
            logger.info("No slug in team payload, team is deleted, returning ...")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        graphql_client = create_github_client(GithubClientType.GRAPHQL)
        exporter = GraphQLTeamWithMembersExporter(graphql_client)

        data_to_upsert = await exporter.get_resource(
            SingleTeamOptions(slug=team["slug"])
        )

        logger.info(f"Upserting team '{team['slug']}'")

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not {"action", "team", "member"} <= payload.keys():
            return False
        return bool(payload["team"].get("slug"))
