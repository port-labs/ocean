from asyncio import BoundedSemaphore, gather
from typing import Any

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from utils import ObjectKind, init_terraform_client
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.terraform_base_webhook_processor import (
    TerraformBaseWebhookProcessor,
)

MAX_CONCURRENT_ENRICHMENTS = 10


class StateVersionWebhookProcessor(TerraformBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.STATE_VERSION]

    async def _enrich_state_version_with_output(
        self, state_version: dict[str, Any], terraform_client: Any
    ) -> dict[str, Any]:
        state_version_id = state_version["id"]
        try:
            output = await terraform_client.get_state_version_output(state_version_id)
            state_version["__output"] = output
        except Exception as e:
            logger.warning(
                f"Failed to fetch output for state version {state_version_id}: {e}"
            )
            state_version["__output"] = {}
        return state_version

    async def _enrich_with_semaphore(
        self,
        state_version: dict[str, Any],
        terraform_client: Any,
        semaphore: BoundedSemaphore,
    ) -> dict[str, Any]:
        """
        Enrich a state version with output using a semaphore to limit concurrency.
        """
        async with semaphore:
            return await self._enrich_state_version_with_output(
                state_version, terraform_client
            )

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        # Extract workspace and organization info directly from payload
        workspace_name = payload["workspace_name"]
        organization_name = payload["organization_name"]

        terraform_client = init_terraform_client()

        max_concurrent_enrichments = MAX_CONCURRENT_ENRICHMENTS
        semaphore = BoundedSemaphore(max_concurrent_enrichments)

        # Fetch and enrich state versions for the workspace
        enriched_state_versions = []
        async for (
            state_version_batch
        ) in terraform_client.get_state_versions_for_single_workspace(
            workspace_name, organization_name
        ):
            # Enrich each batch concurrently as it arrives
            enriched_batch = await gather(
                *[
                    self._enrich_with_semaphore(sv, terraform_client, semaphore)
                    for sv in state_version_batch
                ],
                return_exceptions=False,
            )
            enriched_state_versions.extend(enriched_batch)

        return WebhookEventRawResults(
            updated_raw_results=enriched_state_versions, deleted_raw_results=[]
        )
