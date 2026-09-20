import asyncio
from typing import Any

from loguru import logger

from github.clients.client_factory import create_github_client_for_org
from github.core.exporters.team_exporter import RestTeamExporter
from github.helpers.utils import (
    ObjectKind,
    enrich_with_organization,
    enrich_with_repository,
)
from github.webhook.events import (
    TEAM_COLLABORATOR_EVENTS,
    TEAM_COLLABORATOR_DELETE_EVENTS,
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
from github.core.options import SingleTeamOptions
from github.webhook.webhook_processors.collaborator_webhook_processor.utils import (
    RECONCILIATION_CONCURRENCY_LIMIT,
    reconcile_collaborator_repos,
    skip_if_affiliation_filtered,
)


class CollaboratorTeamWebhookProcessor(
    BaseRepositoryWebhookProcessor, CollaboratorEventValidator
):

    async def _validate_payload(self, payload: EventPayload) -> bool:
        return await self.validate_team_collaborator_payload(payload)

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return await self.should_process_team_collaborator_event(event)

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.COLLABORATOR]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """Handle team-related webhook events for collaborators."""

        action = payload["action"]
        team_slug = payload["team"]["slug"]
        organization = self.get_webhook_payload_organization(payload)["login"]
        repository = payload["repository"]

        logger.info(
            f"Handling team event: {action} for team {team_slug} of organization: {organization}"
        )

        skipped = skip_if_affiliation_filtered(resource_config)
        if skipped is not None:
            return skipped

        if action not in TEAM_COLLABORATOR_EVENTS:
            logger.info(
                f"Skipping unsupported team event {action} for {team_slug} of organization: {organization}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        rest_client = await create_github_client_for_org(organization)
        team_exporter = RestTeamExporter(rest_client)
        members: list[dict[str, Any]] = []
        async for batch in team_exporter.get_team_members_by_slug(
            SingleTeamOptions(organization=organization, slug=team_slug)
        ):
            members.extend(batch)

        if not members:
            logger.warning(
                f"No team data returned for team {team_slug} of organization: {organization}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if action in TEAM_COLLABORATOR_DELETE_EVENTS:
            semaphore = asyncio.BoundedSemaphore(RECONCILIATION_CONCURRENCY_LIMIT)

            results = await asyncio.gather(
                *(
                    reconcile_collaborator_repos(
                        rest_client=rest_client,
                        organization=organization,
                        member_login=member["login"],
                        member_id=member["id"],
                        repositories=[repository],
                        semaphore=semaphore,
                    )
                    for member in members
                )
            )

            updated = [
                item for result in results for item in result.updated_raw_results
            ]
            deleted = [
                item for result in results for item in result.deleted_raw_results
            ]

            logger.info(
                f"Reconciled {len(members)} members of team {team_slug} for "
                f"repository {repository['name']} in {organization}: "
                f"{len(updated)} still collaborators, {len(deleted)} removed"
            )
            return WebhookEventRawResults(
                updated_raw_results=updated, deleted_raw_results=deleted
            )

        data_to_upsert = [
            enrich_with_organization(
                enrich_with_repository(member.copy(), repository["name"]),
                organization,
            )
            for member in members
        ]

        logger.info(
            f"Upserting {len(data_to_upsert)} collaborators for team {team_slug} of organization: {organization}"
        )

        return WebhookEventRawResults(
            updated_raw_results=data_to_upsert, deleted_raw_results=[]
        )
