from loguru import logger
from github.core.exporters.team_exporter import RestTeamExporter
from github.core.options import SingleTeamOptions
from github.webhook.events import TEAM_DELETE_EVENTS, TEAM_UPSERT_EVENTS
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


class TeamWebhookProcessor(_GithubAbstractWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        if not event.payload.get("action"):
            return False

        if event.payload["action"] not in (TEAM_UPSERT_EVENTS + TEAM_DELETE_EVENTS):
            return False

        return event.headers.get("x-github-event") == "team"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.TEAM]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        team = payload["team"]

        logger.info(f"Processing org event: {action}")

        if action in TEAM_DELETE_EVENTS:
            logger.info(f"Team {team['name']} was removed from org")

            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[team]
            )

        client = create_github_client(GithubClientType.REST)
        exporter = RestTeamExporter(client)

        data_to_upsert = await exporter.get_resource(
            SingleTeamOptions(slug=team["slug"])
        )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not {"action", "team"} <= payload.keys():
            return False

        return bool(payload["team"].get("slug"))
