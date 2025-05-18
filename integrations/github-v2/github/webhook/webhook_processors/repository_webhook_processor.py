from loguru import logger
from github.webhook.events import REPOSITORY_DELETE_EVENTS, REPOSITORY_UPSERT_EVENTS
from github.utils import ObjectKind
from github.clients.client_factory import create_github_client
from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.exporters.repository_exporter import RepositoryExporter


class RepositoryWebhookProcessor(_GithubAbstractWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == ObjectKind.REPOSITORY

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPOSITORY]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        repo = payload["repository"]
        name = repo["name"]

        logger.info(f"Processing repository event: {action} for {name}")

        if action in REPOSITORY_DELETE_EVENTS:
            logger.info(f"Repository {name} was {action}")

            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[repo]
            )
        exporter = RepositoryExporter(create_github_client())
        data_to_upsert = await exporter.get_resource(name)

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not {"action", "repository"} <= payload.keys():
            return False

        if payload["action"] not in (
            REPOSITORY_UPSERT_EVENTS + REPOSITORY_DELETE_EVENTS
        ):
            return False

        return bool(payload["repository"].get("name"))
