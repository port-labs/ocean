from typing import Any, Optional, Dict
from loguru import logger
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)
from azure_devops.misc import Kind
from azure_devops.webhooks.events import RepositoryEvents


class RepositoryWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.REPOSITORY]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            event_type = event.payload["eventType"]
            return bool(RepositoryEvents(event_type))
        except ValueError:
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        repository_id = payload["resource"]["repository"]["id"]
        repository = await self._get_repository_data(repository_id)

        return WebhookEventRawResults(
            updated_raw_results=[repository] if repository else [],
            deleted_raw_results=[],
        )

    async def _get_repository_data(
        self, repository_id: str
    ) -> Optional[Dict[str, Any]]:
        repository = await AzureDevopsClient.create_from_ocean_config().get_repository(
            repository_id
        )
        if not repository:
            logger.warning(f"Repository with ID {repository_id} not found")
            return None

        return {"kind": Kind.REPOSITORY, **repository}
