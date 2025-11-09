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


class RunWebhookProcessor(TerraformBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.RUN]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        run_id = payload["run_id"]
        logger.info(f"Processing Terraform run event for run: {run_id}")

        terraform_client = init_terraform_client()
        run = await terraform_client.get_single_run(run_id)

        return WebhookEventRawResults(updated_raw_results=[run], deleted_raw_results=[])
