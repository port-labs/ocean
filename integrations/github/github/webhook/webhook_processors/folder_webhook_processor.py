from loguru import logger
from github.webhook.events import REPOSITORY_DELETE_EVENTS, REPOSITORY_UPSERT_EVENTS
from github.helpers.utils import ObjectKind
from github.clients.client_factory import create_github_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from github.core.options import SingleRepositoryOptions
from github.core.exporters.repository_exporter import RestRepositoryExporter


class FolderWebhookProcessor(_GithubAbstractWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "push"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.FOLDER]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        repo = payload["repository"]
        name = repo["name"]

        logger.info(f"Processing repository push event  for {name}")

        rest_client = create_github_client()
        exporter = RestRepositoryExporter(rest_client)

        data_to_upsert = await exporter.get_resource(SingleRepositoryOptions(name=name))

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
