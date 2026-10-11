from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field, model_validator

from actions.abstract_action_input import AbstractAnthropicActionInput
from actions.abstract_executor import AbstractAnthropicExecutor
from integration import ObjectKind

UPDATING_STATUS_LABEL = "Updating environment"
UPDATE_FAILED_STATUS_LABEL = "Update failed"
ENVIRONMENT_UPDATED_STATUS_LABEL = "Environment updated"


class UpdateEnvironmentInputs(AbstractAnthropicActionInput):
    environmentId: str = Field(min_length=1)
    name: str | None = None
    description: str | None = None
    scope: str | None = None
    config: dict[str, Any] | None = None

    @model_validator(mode="after")
    def at_least_one_update_field(self) -> "UpdateEnvironmentInputs":
        if not any([self.name, self.description, self.scope, self.config]):
            raise ValueError(
                "at least one of name, description, scope, or config must be provided"
            )
        return self

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        data = super().model_dump(**kwargs)
        data.pop("environmentId", None)
        return {field: value for field, value in data.items() if value}


class UpdateEnvironmentExecutor(AbstractAnthropicExecutor):
    """Executor for the `update_environment` action.

    Updates a Claude managed environment's configuration and reflects the
    result into the catalog synchronously. Unlike agent updates, the
    environments API does not use optimistic concurrency via a version field.

    Runs are serialized per environment id so two concurrent updates on the
    same environment do not race each other.
    """

    ACTION_NAME = "update_environment"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return run.execution_properties.get("environmentId")

    async def execute(self, run: IntegrationRun) -> None:
        inputs = UpdateEnvironmentInputs.from_execution_properties(
            run.execution_properties
        )
        environment_id = inputs.environmentId

        await ocean.port_client.post_run_log(
            run,
            f"Updating Claude environment {environment_id}",
            status_label=UPDATING_STATUS_LABEL,
            should_raise=False,
        )

        try:
            environment = await self.client.update_environment(
                environment_id,
                payload=inputs.model_dump(exclude_none=True),
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to update environment {environment_id}: {error}",
                status_label=UPDATE_FAILED_STATUS_LABEL,
            ) from error

        logger.info(f"Updated Claude environment {environment_id} for run {run.id}")

        await self.register_entity(
            ObjectKind.ENVIRONMENT, environment.to_dict(mode="json"), run
        )

        if isinstance(run, WorkflowNodeRun):
            run.output["environmentId"] = environment_id

        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Updated environment {environment_id}",
            status_label=ENVIRONMENT_UPDATED_STATUS_LABEL,
        )
