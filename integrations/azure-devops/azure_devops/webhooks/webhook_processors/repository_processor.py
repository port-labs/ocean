from typing import Any, Optional, Dict, cast

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.misc import Kind
from azure_devops.webhooks.events import RepositoryEvents
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)
from integration import AzureDevopsRepositoryResourceConfig
from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class RepositoryWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.REPOSITORY]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        return payload["resource"].get("repository", {}).get("id") is not None

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
        client = AzureDevopsClient.create_from_ocean_config()
        repository = await self._get_repository_data(client, repository_id)
        if not repository:
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        selector = cast(AzureDevopsRepositoryResourceConfig, resource_config).selector
        included_files = selector.included_files or []
        if included_files:
            from azure_devops.enrichments.included_files import (
                IncludedFilesEnricher,
                RepositoryIncludedFilesStrategy,
            )

            enricher = IncludedFilesEnricher(
                client=client,
                strategy=RepositoryIncludedFilesStrategy(included_files=included_files),
            )
            repository = (await enricher.enrich_batch([repository]))[0]

        return WebhookEventRawResults(
            updated_raw_results=[repository],
            deleted_raw_results=[],
        )

    @staticmethod
    async def _get_repository_data(
        client: AzureDevopsClient, repository_id: str
    ) -> Optional[Dict[str, Any]]:
        repository = await client.get_repository(repository_id)
        if not repository:
            logger.warning(f"Repository with ID {repository_id} not found")
            return None

        return {"kind": Kind.REPOSITORY, **repository}
