from typing import Any, Dict, List, cast

from loguru import logger

from github.clients.client_factory import create_github_client
from github.core.exporters.team_exporter import (
    RestTeamExporter,
)
from github.core.options import SingleTeamOptions
from github.helpers.utils import (
    enrich_with_repository,
    enrich_with_organization,
)
from github.webhook.events import (
    COLLABORATOR_EVENTS,
    COLLABORATOR_UPSERT_EVENTS,
)
from github.webhook.webhook_processors.collaborator_webhook_processor.base_collaborator_webhook_processor import (
    BaseCollaboratorWebhookProcessor,
)
from integration import GithubCollaboratorConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class CollaboratorMembershipWebhookProcessor(BaseCollaboratorWebhookProcessor):

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

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle membership-related webhook events for collaborators."""

        action = payload["action"]
        member = payload["member"]
        team_slug = payload["team"]["slug"]
        member_login = member["login"]
        organization = self.get_webhook_payload_organization(payload)["login"]
        config = cast(GithubCollaboratorConfig, resource_config)

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

        affiliation = config.selector.affiliation
        updated_raw_results: List[Dict[str, Any]] = []
        deleted_raw_results: List[Dict[str, Any]] = []
        repo_cache: Dict[str, set[str]] = {}

        for repo in repositories:
            repo_name = repo["name"]
            if await self.affiliation_matches(
                organization=organization,
                repo_name=repo_name,
                username=member_login,
                affiliation=affiliation,
                repo_collaborators_cache=repo_cache,
            ):
                updated_raw_results.append(
                    enrich_with_organization(
                        enrich_with_repository(member.copy(), repo_name, repo=repo),
                        organization,
                    )
                )
            else:
                deleted_raw_results.append(
                    self.collaborator_delete_payload(
                        organization=organization,
                        repo_name=repo_name,
                        repository=repo,
                        username=member_login,
                        user_id=member["id"],
                    )
                )

        logger.info(
            f"Affiliation selector='{affiliation}' for {member_login} in team {team_slug} of {organization}: "
            f"upserts={len(updated_raw_results)}, deletions={len(deleted_raw_results)}"
        )

        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )
