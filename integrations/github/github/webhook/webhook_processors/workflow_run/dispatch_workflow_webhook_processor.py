from github.actions.utils import (
    CONCLUSION_STATUS_LABELS as CONCLUSION_STATUS_LABELS,
    build_external_id,
    report_workflow_run_conclusion,
)
from github.clients.auth import get_auth_provider
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
    - The actor matches the integration (or any actor when identity
      propagation is enabled — user-token dispatches show the user as actor)
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
        workflow_run_actor = (workflow_run.get("actor") or {}).get("login")
        workflow_run_status = workflow_run.get("status")
        with logger.contextualize(
            workflow_run_id=workflow_run.get("id"),
            workflow_run_actor=workflow_run_actor,
            workflow_run_status=workflow_run_status,
        ):
            if workflow_run_status != "completed":
                logger.debug("Skipping workflow run event as it's not completed yet")
                return False

            # With identity propagation, dispatch uses the user's OAuth token so
            # workflow_run.actor is the user, not the GitHub App / integration PAT.
            # handle_event still gates on external_id + reportWorkflowStatus.
            if ocean.config.identity_propagation.enabled:
                return True

            integration_actor = await get_auth_provider().get_integration_actor()
            if workflow_run_actor == integration_actor:
                return True

            logger.debug(
                "Skipping workflow run event as it was not triggered by this integration",
                integration_actor=integration_actor,
            )
            return False

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
            await report_workflow_run_conclusion(run, workflow_run)

        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
