from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    WebhookProcessorType,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from gitlab.actions.pipeline_completion import (
    TERMINAL_PIPELINE_STATUSES,
    complete_run_if_in_progress,
    find_run_with_retry,
)
from gitlab.actions.utils import build_external_id
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)


class TriggerPipelineWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["pipeline"]
    hooks = ["Pipeline Hook"]

    @classmethod
    def get_processor_type(cls) -> WebhookProcessorType:
        return WebhookProcessorType.ACTION

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return []

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if not await super().should_process_event(event):
            return False
        status = event.payload.get("object_attributes", {}).get("status")
        return status in TERMINAL_PIPELINE_STATUSES

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        project_id = payload.get("project", {}).get("id")
        pipeline_id = payload.get("object_attributes", {}).get("id")
        status = payload.get("object_attributes", {}).get("status")

        external_id = build_external_id(project_id, pipeline_id)
        run = await find_run_with_retry(external_id)

        if run is None:
            logger.debug(
                f"No Port run for pipeline {pipeline_id} (project {project_id}), skipping"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        await complete_run_if_in_progress(run, status, completion_source="webhook")

        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
