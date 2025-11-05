from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from utils import ObjectKind, init_terraform_client
from enrich import enrich_workspace_with_tags
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from webhook_processors.terraform_base_webhook_processor import (
    TerraformBaseWebhookProcessor,
)


class WorkspaceWebhookProcessor(TerraformBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.WORKSPACE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        workspace_id = payload["workspace_id"]
        logger.info(
            f"Processing Terraform workspace event for workspace: {workspace_id}"
        )

        terraform_client = init_terraform_client()
        workspace = await terraform_client.get_single_workspace(workspace_id)
        enriched_workspace = await enrich_workspace_with_tags(
            terraform_client, workspace
        )

        return WebhookEventRawResults(
            updated_raw_results=[enriched_workspace], deleted_raw_results=[]
        )
