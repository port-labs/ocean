from github.actions.utils import build_external_id
from github.context.auth import get_authenticated_user
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
from port_ocean.core.models import (
    ActionRun,
    RunStatus,
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
        authenticated_user = await get_authenticated_user()
        should_process = (
            workflow_run["status"] == "completed"
            and workflow_run["actor"]["login"] == authenticated_user.login
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
        action_run: ActionRun | None = await ocean.port_client.get_run_by_external_id(
            external_id
        )

        if (
            action_run
            and action_run.status == RunStatus.IN_PROGRESS
            and action_run.payload.integrationActionExecutionProperties.get(
                "reportWorkflowStatus", False
            )
        ):
            status = (
                RunStatus.SUCCESS
                if workflow_run["conclusion"] in ["success", "skipped", "neutral"]
                else RunStatus.FAILURE
            )
            logger.info(
                f"Updating action run {action_run.id} status to {status}",
                action_run_id=action_run.id,
                status=status,
            )
            await ocean.port_client.patch_run(action_run.id, {"status": status})

        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
