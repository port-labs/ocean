from github.actions.utils import build_external_id
from github.context.auth import get_authenticated_actor
from github.webhook.webhook_processors.workflow_run.base_workflow_run_webhook_processor import (
    BaseWorkflowRunWebhookProcessor,
)
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    WebhookProcessorType,
)
from loguru import logger


class DispatchWorkflowWebhookProcessor(BaseWorkflowRunWebhookProcessor):
    """
    Webhook processor for handling GitHub workflow run completion events.

    This processor is responsible for:
    1. Filtering workflow_run events to only process completed runs
    2. Verifying that the run was triggered by the authenticated user
    3. Updating the Port action run status based on the workflow conclusion
    4. Handling the mapping between GitHub run IDs and Port run IDs

    The processor only handles events where:
    - The event type is workflow_run
    - The workflow run status is "completed"
    - The actor matches the authenticated GitHub user
    - The run has a matching Port action run ID

    Attributes:
        Inherits all attributes from BaseWorkflowRunWebhookProcessor
    """

    @classmethod
    def get_processor_type(cls) -> WebhookProcessorType:
        return WebhookProcessorType.ACTION

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """
        Determine if this webhook event should be processed.
        """
        if not (await super()._should_process_event(event)):
            return False

        workflow_run = event.payload["workflow_run"]
        actor = await get_authenticated_actor()
        should_process = (
            workflow_run["status"] == "completed"
            and workflow_run["actor"]["login"] == actor
        )

        return should_process

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        """
        Handle a workflow run completion webhook event.
        """
        workflow_run = payload["workflow_run"]
        external_id = build_external_id(workflow_run)

        run = await ocean.port_client.find_run_by_external_id(external_id)
        if (
            run
            and ocean.port_client.is_run_in_progress(run)
            and run.execution_properties.get("reportWorkflowStatus", False)
        ):
            conclusion = workflow_run["conclusion"]
            success = conclusion in ("success", "skipped", "neutral")
            logger.info(
                f"Updating run {run.id} with workflow conclusion: {conclusion}",
                run_id=run.id,
                conclusion=conclusion,
            )
            await ocean.port_client.report_run_completed(
                run, success, f"Workflow completed: {conclusion}"
            )

        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
