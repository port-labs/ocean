from loguru import logger

from github.clients.client_factory import create_github_client
from github.core.exporters.collaborator_exporter import RestCollaboratorExporter
from github.core.options import SingleCollaboratorOptions
from github.helpers.utils import ObjectKind
from github.webhook.events import (
    COLLABORATOR_DELETE_EVENTS,
    COLLABORATOR_EVENTS,
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


class CollaboratorMemberWebhookProcessor(BaseRepositoryWebhookProcessor):

    async def _validate_payload(self, payload: EventPayload) -> bool:
        has_required_fields = not ({"action", "repository", "member"} - payload.keys())

        return has_required_fields and "login" in payload.get("member", {})

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return (
            event.headers.get("x-github-event") == "member"
            and event.payload.get("action") in COLLABORATOR_EVENTS
        )

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.COLLABORATOR]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:

        action = payload["action"]
        repository = payload["repository"]
        repo_name = repository["name"]
        username = payload["member"]["login"]

        logger.info(f"Processing member event: {action} for {username} in {repo_name}")

        if action in COLLABORATOR_DELETE_EVENTS:
            logger.info(
                f"Collaborator {username} was removed from repository {repo_name}"
            )
            data_to_delete = {
                "login": username,
                "id": payload["member"]["id"],
                "__repository": repo_name,
            }
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[data_to_delete]
            )

        logger.info(f"Creating REST client and exporter for collaborator {username}")
        rest_client = create_github_client()
        exporter = RestCollaboratorExporter(rest_client)

        data_to_upsert = await exporter.get_resource(
            SingleCollaboratorOptions(repo_name=repo_name, username=username)
        )
        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
