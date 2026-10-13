from typing import Any

from loguru import logger

from github.clients.client_factory import create_github_client_for_org
from github.core.exporters.team_exporter import (
    RestTeamExporter,
)
from github.core.options import SingleTeamOptions
from github.helpers.utils import (
    ObjectKind,
    enrich_with_repository,
    enrich_with_organization,
)
from github.webhook.events import (
    COLLABORATOR_DELETE_EVENTS,
    COLLABORATOR_UPSERT_EVENTS,
)
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
    CollaboratorEventValidator,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.collaborator_webhook_processor.utils import (
    reconcile_collaborator_repos,
    skip_if_affiliation_filtered,
)


class CollaboratorMembershipWebhookProcessor(
    BaseRepositoryWebhookProcessor, CollaboratorEventValidator
):

    async def validate_payload(self, payload: EventPayload) -> bool:
        return await self._validate_payload(payload)

    async def _validate_payload(self, payload: EventPayload) -> bool:
        return await self.validate_membership_collaborator_payload(payload)

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return await self.should_process_membership_collaborator_event(event)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.COLLABORATOR]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:

        action = payload["action"]
        member = payload["member"]
        team_slug = payload["team"]["slug"]
        member_login = member["login"]
        organization = self.get_webhook_payload_organization(payload)["login"]

        logger.info(
            f"Handling membership event: {action} for {member_login} in team {team_slug}"
        )

        skipped = skip_if_affiliation_filtered(resource_config)
        if skipped is not None:
            return skipped

        rest_client = await create_github_client_for_org(organization)
        team_exporter = RestTeamExporter(rest_client)

        repositories: list[dict[str, Any]] = []
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

        if not repositories:
            logger.debug(
                f"No visible repositories for team {team_slug} in {organization}, "
                f"skipping processing for {member_login}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if action in COLLABORATOR_DELETE_EVENTS:
            logger.info(
                f"Reconciling collaborator {member_login} across {len(repositories)} "
                f"repositories for team {team_slug} in {organization}"
            )
            updated, deleted = await reconcile_collaborator_repos(
                rest_client=rest_client,
                organization=organization,
                member_login=member_login,
                member_id=member["id"],
                repositories=repositories,
            )
            return WebhookEventRawResults(
                updated_raw_results=updated, deleted_raw_results=deleted
            )

        if action not in COLLABORATOR_UPSERT_EVENTS:
            logger.info(
                f"Skipping unsupported membership event {action} for "
                f"{member_login} in team {team_slug} of organization: {organization}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        list_data_to_upsert = self._enrich_collaborators_with_repositories(
            member, repositories, organization
        )

        logger.info(
            f"Upserting {len(list_data_to_upsert)} collaborators for member {member_login} in team {team_slug} of organization: {organization}"
        )

        return WebhookEventRawResults(
            updated_raw_results=list_data_to_upsert, deleted_raw_results=[]
        )

    def _enrich_collaborators_with_repositories(
        self,
        response: dict[str, Any],
        repositories: list[dict[str, Any]],
        organization: str,
    ) -> list[dict[str, Any]]:
        return [
            enrich_with_organization(
                enrich_with_repository(response.copy(), repository["name"]),
                organization,
            )
            for repository in repositories
        ]
