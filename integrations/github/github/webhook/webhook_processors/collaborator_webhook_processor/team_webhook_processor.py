from loguru import logger

from github.clients.client_factory import create_github_client
from github.core.exporters.team_exporter import (
    GraphQLTeamMembersAndReposExporter,
)
from github.helpers.utils import (
    GithubClientType,
    ObjectKind,
    enrich_with_organization,
    enrich_with_repository,
)
from github.webhook.events import (
    TEAM_COLLABORATOR_EVENTS,
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
from github.core.options import SingleTeamOptions
from typing import Any, Dict, List, Optional, cast


class CollaboratorTeamWebhookProcessor(BaseCollaboratorWebhookProcessor):
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
        organization = self.get_webhook_payload_organization(payload)["login"]
        config = cast(GithubCollaboratorConfig, resource_config)
        affiliation = config.selector.affiliation

        logger.info(
            f"Handling team event: {action} for team {team_slug} of organization: {organization}"
        )

        if action not in TEAM_COLLABORATOR_EVENTS:
            logger.info(
                f"Skipping unsupported team event {action} for {team_slug} of organization: {organization}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        graphql_client = create_github_client(client_type=GithubClientType.GRAPHQL)
        team_exporter = GraphQLTeamMembersAndReposExporter(graphql_client)
        team_data = await team_exporter.get_resource(
            SingleTeamOptions(organization=organization, slug=team_slug)
        )

        if not team_data:
            logger.warning(
                f"No team data returned for team {team_slug} of organization: {organization}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        members: List[Dict[str, Any]] = team_data.get("members", {}).get("nodes", [])
        repos: List[Dict[str, Any]] = team_data.get("repositories", {}).get("nodes", [])
        repo_cache: Dict[str, set[str]] = {}

        filtered_repos: List[Dict[str, Any]] = []
        for repo in repos:
            visibility = repo.get("visibility")
            if visibility and not await self.validate_repository_visibility(visibility):
                logger.info(
                    f"Skipping repository {repo.get('name')} due to visibility validation of organization: {organization}"
                )
                continue
            filtered_repos.append(repo)

        updated_raw_results: list[dict[str, Any]] = []
        deleted_raw_results: list[dict[str, Any]] = []

        if affiliation == "all":
            (
                updated_raw_results,
                deleted_raw_results,
            ) = self._build_enriched_collaborator_data(
                repos=filtered_repos,
                members=members,
                organization=organization,
            )
        else:
            for repo in filtered_repos:
                repo_name = repo["name"]
                matching_members: list[dict[str, Any]] = []
                non_matching_members: list[dict[str, Any]] = []

                for member in members:
                    member_login = member["login"]
                    if await self.affiliation_matches(
                        organization=organization,
                        repo_name=repo_name,
                        username=member_login,
                        affiliation=affiliation,
                        repo_collaborators_cache=repo_cache,
                    ):
                        matching_members.append(member)
                    else:
                        non_matching_members.append(member)

                u, d = self._build_enriched_collaborator_data(
                    repos=[repo],
                    members=matching_members,
                    organization=organization,
                    non_matching_members=non_matching_members,
                )
                updated_raw_results.extend(u)
                deleted_raw_results.extend(d)

        logger.info(
            f"Affiliation selector='{affiliation}' for team {team_slug} of {organization}: "
            f"upserts={len(updated_raw_results)}, deletions={len(deleted_raw_results)}"
        )

        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )

    def _build_enriched_collaborator_data(
        self,
        repos: List[Dict[str, Any]],
        members: List[Dict[str, Any]],
        organization: str,
        non_matching_members: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if non_matching_members is None:
            non_matching_members = []

        updated_raw_results: List[Dict[str, Any]] = []
        deleted_raw_results: List[Dict[str, Any]] = []

        for repo in repos:
            repo_name = repo["name"]

            for member in members:
                collaborator = {
                    "id": member["id"],
                    "login": member["login"],
                    "name": member.get("name"),
                    "site_admin": member.get("isSiteAdmin"),
                }

                updated_raw_results.append(
                    enrich_with_organization(
                        enrich_with_repository(collaborator, repo_name, repo=repo),
                        organization,
                    )
                )

            for member in non_matching_members:
                deleted_raw_results.append(
                    self.collaborator_delete_payload(
                        organization=organization,
                        repo_name=repo_name,
                        repository=repo,
                        username=member["login"],
                        user_id=member["id"],
                    )
                )

        return updated_raw_results, deleted_raw_results
