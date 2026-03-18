from loguru import logger

from github.clients.client_factory import create_github_client
from github.core.exporters.collaborator_exporter import RestCollaboratorExporter
from github.core.options import SingleCollaboratorOptions
from github.helpers.utils import (
    enrich_with_organization,
    enrich_with_repository,
)
from github.webhook.events import (
    COLLABORATOR_DELETE_EVENTS,
    COLLABORATOR_EVENTS,
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
from typing import cast


class CollaboratorMemberWebhookProcessor(BaseCollaboratorWebhookProcessor):

    async def _validate_payload(self, payload: EventPayload) -> bool:
        has_required_fields = not ({"action", "repository", "member"} - payload.keys())

        return has_required_fields and "login" in payload.get("member", {})

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.headers.get("x-github-event") == "member"
            and event.payload.get("action") in COLLABORATOR_EVENTS
        )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:

        action = payload["action"]
        repository = payload["repository"]
        repo_name = repository["name"]
        username = payload["member"]["login"]
        organization = self.get_webhook_payload_organization(payload)["login"]
        config = cast(GithubCollaboratorConfig, resource_config)

        logger.info(
            f"Processing member event: {action} for {username} in {repo_name} of organization: {organization}"
        )

        if action in COLLABORATOR_DELETE_EVENTS:
            logger.info(
                f"Collaborator {username} was removed from repository {repo_name} of organization: {organization}"
            )
            constructed_payload = {
                "login": username,
                "id": payload["member"]["id"],
            }

            data_to_delete = enrich_with_organization(
                enrich_with_repository(constructed_payload, repo_name, repo=repository),
                organization,
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[data_to_delete]
            )

        repo_cache: dict[str, set[str]] = {}
        if not await self.affiliation_matches(
            organization=organization,
            repo_name=repo_name,
            username=username,
            affiliation=config.selector.affiliation,
            repo_collaborators_cache=repo_cache,
        ):
            logger.info(
                f"Collaborator {username} in {repo_name} does not match affiliation "
                f"selector '{config.selector.affiliation}', emitting deletion"
            )
            return self.collaborator_delete_result(
                organization=organization,
                repo_name=repo_name,
                repository=repository,
                username=username,
                user_id=payload["member"]["id"],
            )

        logger.info(
            f"Creating REST client and exporter for collaborator {username} of organization: {organization}"
        )
        rest_client = create_github_client()
        exporter = RestCollaboratorExporter(rest_client)

        data_to_upsert = await exporter.get_resource(
            SingleCollaboratorOptions(
                organization=organization, repo_name=repo_name, username=username
            )
        )
        if not data_to_upsert:
            logger.info(
                f"Collaborator {username} in {repo_name} does not exist, skipping upsert"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
