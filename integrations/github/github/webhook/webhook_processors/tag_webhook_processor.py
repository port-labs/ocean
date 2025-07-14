from loguru import logger
from github.helpers.utils import ObjectKind
from github.clients.client_factory import create_github_client
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.options import SingleTagOptions
from github.core.exporters.tag_exporter import RestTagExporter


class TagWebhookProcessor(BaseRepositoryWebhookProcessor):
    _event_type: str | None = None
    _allowed_tag_events = ["create", "delete"]

    async def _validate_payload(self, payload: EventPayload) -> bool:
        return "ref" in payload

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.headers.get("x-github-event")
        if event_type not in self._allowed_tag_events:
            return False

        self._event_type = event_type
        return event.payload.get("ref_type") == "tag"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.TAG]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        tag_ref = payload["ref"]
        repo = payload["repository"]
        repo_name = repo["name"]

        logger.info(
            f"Processing tag event: {self._event_type} for tag {tag_ref} in {repo_name}"
        )

        if self._event_type == "delete":
            data_to_delete = {"name": tag_ref}
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[data_to_delete]
            )

        rest_client = create_github_client()
        exporter = RestTagExporter(rest_client)

        data_to_upsert = await exporter.get_resource(
            SingleTagOptions(repo_name=repo_name, tag_name=tag_ref)
        )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
