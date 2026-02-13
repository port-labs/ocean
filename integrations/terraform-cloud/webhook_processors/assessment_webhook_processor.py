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
from client import HealthAssessmentEvents, HEALTH_ASSESSMENT_TRIGGER_SCOPE


class AssessmentWebhookProcessor(TerraformBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.HEALTH_ASSESSMENT]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        try:
            if event.payload.get("trigger_scope") != HEALTH_ASSESSMENT_TRIGGER_SCOPE:
                return False
            trigger = event.payload["trigger"]
            return bool(HealthAssessmentEvents(trigger))
        except (KeyError, ValueError):
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        assessment_id = payload["details"]["new_assessment_result"]["id"]
        logger.info(
            f"Processing Terraform health assessment event for result: {assessment_id}"
        )

        terraform_client = init_terraform_client()
        assessment = await terraform_client.get_single_health_assessment(assessment_id)
        return WebhookEventRawResults(
            updated_raw_results=[assessment], deleted_raw_results=[]
        )
