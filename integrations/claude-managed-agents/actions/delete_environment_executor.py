from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from actions.abstract_action_input import AbstractAnthropicActionInput
from actions.abstract_executor import AbstractAnthropicExecutor
from integration import ObjectKind

DELETING_STATUS_LABEL = "Deleting environment"
DELETE_FAILED_STATUS_LABEL = "Deletion failed"
ENVIRONMENT_DELETED_STATUS_LABEL = "Environment deleted"


class DeleteEnvironmentInputs(AbstractAnthropicActionInput):
    environmentId: str = Field(min_length=1)


class DeleteEnvironmentExecutor(AbstractAnthropicExecutor):
    """Executor for the `delete_environment` action.

    Permanently deletes a Claude managed environment. Unlike agents (which
    can only be archived), environments support hard deletion. Sessions that
    were already created against this environment are not affected.
    The run completes synchronously: no async webhook is involved.

    Runs are serialized per environment id so two concurrent delete attempts
    on the same environment do not race each other.
    """

    ACTION_NAME = "delete_environment"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return run.execution_properties.get("environmentId")

    async def execute(self, run: IntegrationRun) -> None:
        inputs = DeleteEnvironmentInputs.from_execution_properties(
            run.execution_properties
        )
        environment_id = inputs.environmentId

        await ocean.port_client.post_run_log(
            run,
            f"Deleting Claude environment {environment_id}",
            status_label=DELETING_STATUS_LABEL,
            should_raise=False,
        )

        try:
            await self.client.delete_environment(environment_id)
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to delete environment {environment_id}: {error}",
                status_label=DELETE_FAILED_STATUS_LABEL,
            ) from error

        logger.info(f"Deleted Claude environment {environment_id} for run {run.id}")

        await self.deregister_entity(
            ObjectKind.ENVIRONMENT, {"id": environment_id}, run
        )

        if isinstance(run, WorkflowNodeRun):
            run.output["environmentId"] = environment_id

        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Deleted environment {environment_id}",
            status_label=ENVIRONMENT_DELETED_STATUS_LABEL,
        )
