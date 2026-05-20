from typing import cast

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from utils import ObjectKind, init_terraform_client
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.base_state_webhook_processor import (
    BaseStateWebhookProcessor,
)
from integration import StateFileResourceConfig


class StateFileWebhookProcessor(BaseStateWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.STATE_FILE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        terraform_client = init_terraform_client()
        selector = cast(StateFileResourceConfig, resource_config).selector

        if selector.current_only:
            workspace_id = payload["workspace_id"]
            logger.info(
                f"Fetching current state file for workspace {workspace_id} (currentOnly=true)"
            )
            state_version = (
                await terraform_client.get_current_state_version_for_workspace(
                    workspace_id
                )
            )
            if state_version is None:
                return WebhookEventRawResults(
                    updated_raw_results=[], deleted_raw_results=[]
                )

            state_file = await terraform_client.download_state_file(state_version)
            state_files = [state_file] if state_file else []
        else:
            workspace_name = payload["workspace_name"]
            organization_name = payload["organization_name"]
            logger.info(
                f"Fetching all state files for workspace {workspace_name} (currentOnly=false)"
            )
            state_files = []
            async for (
                state_file_batch
            ) in terraform_client.get_state_file_for_single_workspace(
                workspace_name, organization_name
            ):
                state_files.extend(state_file_batch)

        return WebhookEventRawResults(
            updated_raw_results=state_files, deleted_raw_results=[]
        )
