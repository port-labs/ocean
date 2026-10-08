from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from actions.abstract_action_input import AbstractAnthropicActionInput
from actions.abstract_executor import AbstractAnthropicExecutor
from integration import ObjectKind

CREATING_STATUS_LABEL = "Creating environment"
CREATE_FAILED_STATUS_LABEL = "Creation failed"
ENVIRONMENT_CREATED_STATUS_LABEL = "Environment created"


class CreateEnvironmentInputs(AbstractAnthropicActionInput):
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None
    scope: str | None = None
    config: dict[str, Any] | None = None


class CreateEnvironmentExecutor(AbstractAnthropicExecutor):
    """Executor for the `create_environment` action.

    Creates a Claude managed environment (cloud or self-hosted container
    configuration) and reflects it into the catalog synchronously. There is
    no async webhook for environment creation.
    """

    ACTION_NAME = "create_environment"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = CreateEnvironmentInputs.from_execution_properties(
            run.execution_properties
        )

        await ocean.port_client.post_run_log(
            run,
            f"Creating Claude environment '{inputs.name}'",
            status_label=CREATING_STATUS_LABEL,
            should_raise=False,
        )

        try:
            environment = await self.client.create_environment(
                name=inputs.name,
                description=inputs.description,
                scope=inputs.scope,
                extra=inputs.config,
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to create environment '{inputs.name}': {error}",
                status_label=CREATE_FAILED_STATUS_LABEL,
            ) from error

        environment_id = environment.get("id")
        logger.info(
            f"Created Claude environment {environment_id} for run {run.id}"
        )

        # Reflect the new environment in the catalog via the existing
        # `environment` kind mapping. Environments have no webhook events, so
        # without this the entity would not appear until the next resync.
        # Best-effort: never fails the run.
        await self.register_entity(ObjectKind.ENVIRONMENT, environment, run)

        if isinstance(run, WorkflowNodeRun):
            run.output["environmentId"] = environment_id

        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Created environment {environment_id}",
            status_label=ENVIRONMENT_CREATED_STATUS_LABEL,
        )
