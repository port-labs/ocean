import asyncio
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

    async def _should_process_state(self, payload: EventPayload) -> bool:
        """Check if the run has a state file change."""
        notifications = payload["notifications"]
        for notification in notifications:
            run_status = notification["run_status"]
            # Only process state when run has applied changes
            if run_status == "applied":
                return True
        return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        if not await self._should_process_state(payload):
            logger.info(
                "Run not in applied state, skipping state version webhook processing"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        # Extract workspace and organization info directly from payload
        workspace_name = payload["workspace_name"]
        organization_name = payload["organization_name"]

        terraform_client = init_terraform_client()

        # Fetch and enrich state versions for the workspace
        enriched_state_versions = []
        async for (
            state_version_batch
        ) in terraform_client.get_state_versions_for_single_workspace(
            workspace_name, organization_name
        ):
            # Enrich each batch concurrently as it arrives
            enriched_batch = await asyncio.gather(
                *[
                    self._enrich_state_version_with_output(sv, terraform_client)
                    for sv in state_version_batch
                ],
                return_exceptions=False,
            )
            enriched_state_versions.extend(enriched_batch)

        return WebhookEventRawResults(
            updated_raw_results=enriched_state_versions, deleted_raw_results=[]
        )
