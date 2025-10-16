"""Webhook processor for Harbor repository events."""

from typing import cast
from loguru import logger
from harbor.webhook.events import REPOSITORY_DELETE_EVENTS, REPOSITORY_UPSERT_EVENTS
from harbor.helpers.utils import ObjectKind
from harbor.webhook.harbor_abstract_webhook_processor import (
    HarborAbstractWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from integration import HarborRepositoriesConfig
from harbor.core.options import SingleRepositoryOptions
from harbor.core.exporters.repository_exporter import HarborRepositoryExporter
from initialize_client import init_client


class RepositoryWebhookProcessor(HarborAbstractWebhookProcessor):
    """Webhook processor for Harbor repository events."""

    async def validate_payload(self, payload: EventPayload) -> bool:
        """Validate the payload structure and content."""
        event_type = payload.get("type")
        if not event_type:
            return False

        valid_events = REPOSITORY_UPSERT_EVENTS + REPOSITORY_DELETE_EVENTS
        return event_type in valid_events

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPOSITORIES]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        event_type = payload["type"]
        event_data = payload.get("event_data", {})
        repository = event_data.get("repository", {})

        if not repository:
            logger.warning(f"No repository data in {event_type} event")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(
            f"Processing repository event: {event_type} for {repository.get('repo_full_name')}"
        )

        if event_type in REPOSITORY_DELETE_EVENTS:
            # For delete events, return the repository as deleted
            deleted_repository = {
                "project_id": repository.get("project_id"),
                "repository_id": repository.get("repository_id"),
                "name": repository.get("repo_full_name"),
                "project_name": repository.get("namespace"),
            }

            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[deleted_repository]
            )

        # For upsert events, fetch the latest repository data
        client = init_client()
        exporter = HarborRepositoryExporter(client)
        resource_config = cast(HarborRepositoriesConfig, resource_config)

        try:
            project_name = repository.get("namespace")
            repository_name = repository.get("repo_full_name")

            if not all([project_name, repository_name]):
                logger.warning(f"Missing required data for repository: {repository}")
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

            options = SingleRepositoryOptions(
                project_name=project_name,
                repository_name=repository_name,
            )

            repository_data = await exporter.get_resource(options)
            return WebhookEventRawResults(
                updated_raw_results=[repository_data], deleted_raw_results=[]
            )

        except Exception as e:
            logger.error(f"Failed to fetch repository data for {repository}: {e}")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )
