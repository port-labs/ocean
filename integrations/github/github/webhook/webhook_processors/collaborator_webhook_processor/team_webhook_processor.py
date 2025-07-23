from loguru import logger

from github.clients.client_factory import create_github_client
from github.core.exporters.team_exporter import (
    GraphQLTeamMembersAndReposExporter,
)
from github.helpers.utils import GithubClientType, ObjectKind
from github.webhook.events import (
    TEAM_COLLABORATOR_EVENTS,
)
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.options import SingleTeamOptions


class CollaboratorTeamWebhookProcessor(BaseRepositoryWebhookProcessor):

    async def _validate_payload(self, payload: EventPayload) -> bool:

        has_required_fields = not (
            {"action", "repository", "organization", "team"} - payload.keys()
        )

        has_org_login = "login" in payload.get("organization", {})
        has_team_name = "name" in payload.get("team", {})

        return has_required_fields and has_org_login and has_team_name

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.headers.get("x-github-event") == "team"
            and event.payload.get("action") in TEAM_COLLABORATOR_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.COLLABORATOR]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle team-related webhook events for collaborators."""

        action = payload["action"]
        team_slug = payload["team"]["slug"]

        logger.info(f"Handling team event: {action} for team {team_slug}")

        if action not in TEAM_COLLABORATOR_EVENTS:
            logger.info(f"Skipping unsupported team event {action} for {team_slug}")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        graphql_client = create_github_client(client_type=GithubClientType.GRAPHQL)
        team_exporter = GraphQLTeamMembersAndReposExporter(graphql_client)
        team_data = await team_exporter.get_resource(SingleTeamOptions(slug=team_slug))

        if not team_data:
            logger.warning(f"No team data returned for team {team_slug}")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        data_to_upsert = [
            {
                "id": member["id"],
                "login": member["login"],
                "name": member["name"],
                "site_admin": member["isSiteAdmin"],
                "__repository": repo["name"],
            }
            for member in team_data["members"]["nodes"]
            for repo in team_data["repositories"]["nodes"]
        ]

        logger.info(
            f"Upserting {len(data_to_upsert)} collaborators for team {team_slug}"
        )

        return WebhookEventRawResults(
            updated_raw_results=data_to_upsert, deleted_raw_results=[]
        )
