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


class StateFileWebhookProcessor(TerraformBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.STATE_FILE]

    async def _should_process_state(self, payload: EventPayload) -> bool:
        """Check if the run has a state file change."""
        notifications = payload["notifications"]
        for notification in notifications:
            run_status = notification["run_status"]
            # Only process state when run has applied changes
            if run_status == "applied":
                return True
        return False

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return await self._should_process_state(event.payload)

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        workspace_name = payload["workspace_name"]
        organization_name = payload["organization_name"]

        terraform_client = init_terraform_client()
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
