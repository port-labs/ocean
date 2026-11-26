from typing import Any, Self

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field, model_validator

from azure_integration.foundry.actions.abstract_action_input import (
    AbstractFoundryInvokeInput,
)
from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.clients.http.foundry_client import FoundryApiError
from azure_integration.foundry.helpers.cancel_response import (
    in_progress_response_ids_for_conversation,
    response_cancel_path,
)

CANCELLING_STATUS_LABEL = "Cancelling response"
CANCEL_FAILED_STATUS_LABEL = "Cancel failed"
RESPONSE_CANCELLED_STATUS_LABEL = "Response cancelled"
RESPONSE_NOT_CANCELLABLE_STATUS_LABEL = "Cannot cancel response"


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
        props = run.execution_properties
        response_id = props.get("responseId")
        if response_id:
            return str(response_id)
        conversation_id = props.get("conversationId")
        if conversation_id:
            return str(conversation_id)
        return None

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CancelResponseInputs.from_execution_properties(
            run.execution_properties
        )
        if inputs.responseId:
            response_ids = [inputs.responseId]
        elif inputs.conversationId:
            response_ids = await in_progress_response_ids_for_conversation(
                self.client,
                project_endpoint=inputs.project_endpoint,
                conversation_id=inputs.conversationId,
                agent_id=inputs.agentId,
            )
            if not response_ids:
                raise ActionExecutionError(
                    f"No in-flight Foundry responses for conversation {inputs.conversationId}",
                    status_label=RESPONSE_NOT_CANCELLABLE_STATUS_LABEL,
                )
        else:
            raise ActionExecutionError(
                "responseId or conversationId is required",
                status_label=CANCEL_FAILED_STATUS_LABEL,
            )

        cancelled: list[str] = []
        last_status: str | None = None
        for response_id in response_ids:
            cancel_url = self.client.build_url(
                inputs.project_endpoint,
                response_cancel_path(response_id, inputs.agentId),
            )
            await ocean.port_client.post_run_log(
                run,
                f"Cancelling Foundry response {response_id}",
                status_label=CANCELLING_STATUS_LABEL,
                should_raise=False,
            )
            try:
                payload = await self.client.send_api_request(cancel_url, method="POST")
            except FoundryApiError as error:
                if error.is_skippable_client_error:
                    logger.warning(
                        f"Skip cancel for {response_id}: {error}"
                    )
                    continue
                raise ActionExecutionError(
                    f"Failed to cancel response {response_id}: {error}",
                    status_label=CANCEL_FAILED_STATUS_LABEL,
                ) from error
            except Exception as error:
                raise ActionExecutionError(
                    f"Failed to cancel response {response_id}: {error}",
                    status_label=CANCEL_FAILED_STATUS_LABEL,
                ) from error
            cancelled.append(response_id)
            if isinstance(payload, dict):
                last_status = payload.get("status")

        if not cancelled:
            raise ActionExecutionError(
                "No responses were cancelled",
                status_label=RESPONSE_NOT_CANCELLABLE_STATUS_LABEL,
            )

        logger.info(
            f"Cancelled Foundry response(s) {cancelled} for run {run.id}"
        )

        if isinstance(run, WorkflowNodeRun):
            output: dict[str, Any] = {
                "responseId": cancelled[-1],
                "responseIds": cancelled,
                "projectArmId": inputs.projectArmId,
            }
            if last_status is not None:
                output["status"] = last_status
            if inputs.conversationId:
                output["conversationId"] = inputs.conversationId
            run.output = output

        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Cancelled {len(cancelled)} response(s)",
            status_label=RESPONSE_CANCELLED_STATUS_LABEL,
        )
