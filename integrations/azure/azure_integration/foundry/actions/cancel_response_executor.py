from typing import Self

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field, model_validator

from azure_integration.foundry.actions.abstract_action_input import (
    AbstractFoundryInvokeInput,
)
from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.helpers.cancel_response import (
    in_progress_response_ids_for_conversation,
)
from azure_integration.foundry.helpers.utils import agent_openai_protocol_path

CANCELLING_STATUS_LABEL = "Cancelling response"
CANCEL_FAILED_STATUS_LABEL = "Cancel failed"
RESPONSE_CANCELLED_STATUS_LABEL = "Response cancelled"


class CancelResponseInputs(AbstractFoundryInvokeInput):
    responseId: str | None = Field(default=None, min_length=1)
    conversationId: str | None = Field(default=None, min_length=1)
    agentId: str = Field(min_length=1)

    @model_validator(mode="after")
    def _require_cancel_target(self) -> Self:
        if self.responseId or self.conversationId:
            return self
        raise ValueError("responseId or conversationId is required")


class CancelResponseExecutor(AbstractFoundryExecutor):
    """Cancel a background Foundry Responses API invocation (invoke_agent / invoke_model)."""

    ACTION_NAME = "cancel_response"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return run.execution_properties.get(
            "conversationId"
        ) or run.execution_properties.get("responseId")

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CancelResponseInputs.from_execution_properties(
            run.execution_properties
        )
        response_ids: list[str] = []
        if inputs.conversationId:
            response_ids = await in_progress_response_ids_for_conversation(
                self.client,
                project_endpoint=inputs.project_endpoint,
                conversation_id=inputs.conversationId,
                agent_id=inputs.agentId,
            )
        elif inputs.responseId:
            response_ids.append(inputs.responseId)

        cancelled: list[str] = []
        for response_id in response_ids:
            cancel_url = self.client.build_url(
                inputs.project_endpoint,
                f"{agent_openai_protocol_path(inputs.agentId, 'responses')}/{response_id}/cancel",
            )
            await ocean.port_client.post_run_log(
                run,
                f"Cancelling Foundry response {response_id}",
                status_label=CANCELLING_STATUS_LABEL,
                should_raise=False,
            )
            try:
                await self.client.send_api_request(cancel_url, method="POST")
                cancelled.append(response_id)
            except Exception as error:
                raise ActionExecutionError(
                    f"Failed to cancel response {response_id}: {error}",
                    status_label=CANCEL_FAILED_STATUS_LABEL,
                ) from error

        logger.info(f"Cancelled Foundry response(s) {cancelled} for run {run.id}")

        if isinstance(run, WorkflowNodeRun):
            run.output = {
                "cancelledResponseIds": cancelled,
            }

        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Cancelled {len(cancelled)} response(s)",
            status_label=RESPONSE_CANCELLED_STATUS_LABEL,
        )
