from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    WebhookProcessorType,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from actions.constants import TASK_STATUS_LABELS
from actions.utils import build_external_id
from webhook_processors.abstract_fake_webhook_processor import (
    AbstractFakeWebhookProcessor,
)
from webhook_processors.constants import FAKE_TASK_COMPLETED_EVENT

TERMINAL_TASK_STATUSES = frozenset({"success", "failed"})


class TriggerFakeTaskWebhookProcessor(AbstractFakeWebhookProcessor):
    @classmethod
    def get_processor_type(cls) -> WebhookProcessorType:
        return WebhookProcessorType.ACTION

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return []

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if event.payload.get("event") != FAKE_TASK_COMPLETED_EVENT:
            return False

        task = event.payload.get("task") or {}
        task_id = task.get("id")
        status = task.get("status")
        return task_id is not None and status in TERMINAL_TASK_STATUSES

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        task = payload.get("task") or {}
        task_id = task["id"]
        status = task["status"]

        run = await ocean.port_client.find_run_by_external_id(
            build_external_id(str(task_id))
        )
        if run is None:
            logger.debug(f"No Port run found for fake task {task_id}, skipping")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        success = status == "success"
        await ocean.port_client.post_run_log(
            run,
            f"Fake task completed with status: {status}",
            should_raise=False,
        )
        await ocean.port_client.report_run_completed(
            run,
            success,
            f"Fake task completed: {status}",
            status_label=TASK_STATUS_LABELS.get(status, f"Task {status}"),
        )
        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
