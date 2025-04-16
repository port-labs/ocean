from loguru import logger
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    EventHeaders,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from kinds import Kinds
from initialize_client import create_github_client
from authenticate import authenticate_github_webhook


class TeamWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "team"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.TEAM]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        team_info = payload.get("team", {})
        team_name = team_info.get("name")
        team_slug = team_info.get("slug")
        client = create_github_client()
        logger.info(f"Handling team event: {team_name}")

        org_info = payload.get("organization", {})
        org = org_info.get("login")

        updated_results = []

        if org and team_slug:
            logger.debug(
                f"Fetching updated team data from GitHub for team slug={team_slug}"
            )
            async for team_page in client.fetch_single_github_resource(
                "teams", org=org, team_slug=team_slug
            ):
                if team_page:
                    updated_results.extend(team_page)
            if not updated_results:
                logger.warning(
                    "Could not retrieve updated team data from GitHub. Using webhook payload only."
                )
                updated_results.append(team_info)
        else:
            logger.warning(
                "Missing org or team slug in webhook payload. Skipping GitHub team fetch."
            )
            updated_results.append(team_info)

        return WebhookEventRawResults(
            updated_raw_results=updated_results, deleted_raw_results=[]
        )

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return authenticate_github_webhook(payload, headers)

    async def validate_payload(self, payload: dict) -> bool:
        return True
