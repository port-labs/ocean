from typing import Any, Dict, List

from loguru import logger

from github.clients.client_factory import create_github_client
from github.core.exporters.team_exporter import (
    RestTeamExporter,
)
from github.core.options import SingleTeamOptions
from github.helpers.utils import ObjectKind, enrich_with_repository
from github.webhook.events import (
    COLLABORATOR_EVENTS,
    COLLABORATOR_UPSERT_EVENTS,
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


class CollaboratorMembershipWebhookProcessor(BaseRepositoryWebhookProcessor):

    async def validate_payload(self, payload: EventPayload) -> bool:
        return await self._validate_payload(payload)

    async def _validate_payload(self, payload: EventPayload) -> bool:

        has_required_fields = not (
            {"action", "organization", "team", "member"} - payload.keys()
        )

        has_org_login = "login" in payload.get("organization", {})
        has_team_name = "name" in payload.get("team", {})
        has_member_login = "login" in payload.get("member", {})

        return (
            has_required_fields and has_org_login and has_team_name and has_member_login
        )

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.headers.get("x-github-event") == "membership"
            and event.payload.get("action") in COLLABORATOR_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.COLLABORATOR]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle membership-related webhook events for collaborators."""

        action = payload["action"]
        member = payload["member"]
        team_slug = payload["team"]["slug"]
        member_login = member["login"]
        organization = payload["organization"]["login"]

        logger.info(
            f"Handling membership event: {action} for {member_login} in team {team_slug}"
        )

        if action not in COLLABORATOR_UPSERT_EVENTS:
            # Since we cannot ascertain the repos for which the member was a collaborator,
            logger.info(
                f"Skipping unsupported membership event {action} for {member_login} of organization: {organization}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        rest_client = create_github_client()
        team_exporter = RestTeamExporter(rest_client)

        repositories = []
        async for batch in team_exporter.get_team_repositories_by_slug(
            SingleTeamOptions(organization=organization, slug=team_slug)
        ):
            for repo in batch:
                if not await self.validate_repository_visibility(repo["visibility"]):
                    logger.info(
                        f"Skipping repository {repo['name']} due to visibility validation of organization: {organization}"
                    )
                    continue
                repositories.append(repo)

        list_data_to_upsert = self._enrich_collaborators_with_repositories(
            member, repositories
        )

        logger.info(
            f"Upserting {len(list_data_to_upsert)} collaborators for member {member_login} in team {team_slug} of organization: {organization}"
        )

        return WebhookEventRawResults(
            updated_raw_results=list_data_to_upsert, deleted_raw_results=[]
        )

    def _enrich_collaborators_with_repositories(
        self, response: Dict[str, Any], repositories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Helper function to enrich response with repository information."""
        list_of_collaborators = []
        for repository in repositories:
            collaborator_copy = response.copy()
            list_of_collaborators.append(
                enrich_with_repository(collaborator_copy, repository["name"])
            )
        return list_of_collaborators
