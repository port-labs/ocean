from loguru import logger
from github.webhook.events import RELEASE_DELETE_EVENTS
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
from github.core.options import SingleReleaseOptions
from github.core.exporters.release_exporter import RestReleaseExporter


class ReleaseWebhookProcessor(BaseRepositoryWebhookProcessor):
    async def _validate_payload(self, payload: EventPayload) -> bool:
        return "release" in payload and "id" in payload["release"]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "release"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.RELEASE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        release = payload["release"]
        repo = payload["repository"]
        release_id = release["id"]
        repo_name = repo["name"]

        logger.info(
            f"Processing release event: {action} for release {release_id} in {repo_name}"
        )

        if action in RELEASE_DELETE_EVENTS:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[release]
            )

        rest_client = create_github_client()
        exporter = RestReleaseExporter(rest_client)

        data_to_upsert = await exporter.get_resource(
            SingleReleaseOptions(repo_name=repo_name, release_id=release_id)
        )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
