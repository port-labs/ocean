from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from azure_integration.foundry.actions.abstract_action_input import (
    AbstractFoundryInvokeInput,
)
from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.clients.http.foundry_client import FoundryApiError

CANCELLING_STATUS_LABEL = "Cancelling response"
CANCEL_FAILED_STATUS_LABEL = "Cancel failed"
RESPONSE_CANCELLED_STATUS_LABEL = "Response cancelled"
RESPONSE_NOT_CANCELLABLE_STATUS_LABEL = "Cannot cancel response"


class CancelResponseInputs(AbstractFoundryInvokeInput):
    responseId: str = Field(min_length=1)


class CancelResponseExecutor(AbstractFoundryExecutor):
    """Cancel a background Foundry Responses API invocation (invoke_agent / invoke_model)."""

    ACTION_NAME = "cancel_response"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        response_id = run.execution_properties.get("responseId")
        return str(response_id) if response_id else None

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CancelResponseInputs.from_execution_properties(
            run.execution_properties
        )
        cancel_url = self.client.build_url(
            inputs.project_endpoint,
            f"openai/v1/responses/{inputs.responseId}/cancel",
        )

        await ocean.port_client.post_run_log(
            run,
            f"Cancelling Foundry response {inputs.responseId}",
            status_label=CANCELLING_STATUS_LABEL,
            should_raise=False,
        )

        try:
            payload = await self.client.send_api_request(cancel_url, method="POST")
        except FoundryApiError as error:
            if error.is_skippable_client_error:
                raise ActionExecutionError(
                    f"Response {inputs.responseId} cannot be cancelled: {error}",
                    status_label=RESPONSE_NOT_CANCELLABLE_STATUS_LABEL,
                ) from error
            raise ActionExecutionError(
                f"Failed to cancel response {inputs.responseId}: {error}",
                status_label=CANCEL_FAILED_STATUS_LABEL,
            ) from error
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to cancel response {inputs.responseId}: {error}",
                status_label=CANCEL_FAILED_STATUS_LABEL,
            ) from error

        status = payload.get("status") if isinstance(payload, dict) else None
        logger.info(
            f"Cancelled Foundry response {inputs.responseId} "
            f"(status={status!r}) for run {run.id}"
        )

        if isinstance(run, WorkflowNodeRun):
            output: dict[str, Any] = {
                "responseId": inputs.responseId,
                "projectArmId": inputs.projectArmId,
            }
            if status is not None:
                output["status"] = status
            run.output = output

        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Cancelled response {inputs.responseId}",
            status_label=RESPONSE_CANCELLED_STATUS_LABEL,
        )
