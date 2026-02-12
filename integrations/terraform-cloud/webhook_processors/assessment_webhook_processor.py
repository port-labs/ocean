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


class AssessmentWebhookProcessor(TerraformBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.HEALTH_ASSESSMENT]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        workspace_id = payload["workspace_id"]
        logger.info(f"Processing Terraform assessment event for result: {workspace_id}")

        terraform_client = init_terraform_client()
        assessment = await terraform_client.get_current_health_assessment_for_workspace(
            workspace_id
        )
        return WebhookEventRawResults(
            updated_raw_results=[assessment], deleted_raw_results=[]
        )
