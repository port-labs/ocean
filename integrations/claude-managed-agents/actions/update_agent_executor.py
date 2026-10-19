from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field, model_validator

from actions.abstract_action_input import AbstractAnthropicActionInput
from actions.abstract_executor import AbstractAnthropicExecutor
from actions.port_mcp import apply_port_mcp_to_agent_config
from integration import ObjectKind

UPDATING_STATUS_LABEL = "Updating agent"
UPDATE_FAILED_STATUS_LABEL = "Update failed"
AGENT_UPDATED_STATUS_LABEL = "Agent updated"


class UpdateAgentInputs(AbstractAnthropicActionInput):
    agentId: str = Field(min_length=1)
    name: str | None = None
    model: str | None = None
    systemPrompt: str | None = None
    config: dict[str, Any] | None = None
    enablePortMcp: bool | None = None

    @model_validator(mode="after")
    def at_least_one_update_field(self) -> "UpdateAgentInputs":
        if not any(
            [
                self.name,
                self.model,
                self.systemPrompt,
                self.config is not None,
                self.enablePortMcp is not None,
            ]
        ):
            raise ValueError(
                "at least one of name, model, systemPrompt, config, or "
                "enablePortMcp must be provided"
            )
        return self

    def to_request_payload(self) -> dict[str, Any]:
        payload = self.model_dump(
            exclude={"agentId", "config", "enablePortMcp"}, exclude_none=True
        )
        if "systemPrompt" in payload:
            payload["system"] = payload.pop("systemPrompt")

        config = self.config or {}
        if self.enablePortMcp is True:
            config = apply_port_mcp_to_agent_config(config)
        return {**payload, **config}


class UpdateAgentExecutor(AbstractAnthropicExecutor):
    """Executor for the `update_agent` action.

    Retrieves the agent's current version (required by the Anthropic API for
    optimistic concurrency), applies the requested changes, and completes the
    run synchronously.

    Runs are serialized per agent id so two concurrent updates on the same
    agent do not race each other on the version field.
    """

    ACTION_NAME = "update_agent"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return run.execution_properties.get("agentId")

    async def execute(self, run: IntegrationRun) -> None:
        inputs = UpdateAgentInputs.from_execution_properties(run.execution_properties)
        agent_id = inputs.agentId

        await ocean.port_client.post_run_log(
            run,
            f"Updating Claude agent {agent_id}",
            status_label=UPDATING_STATUS_LABEL,
            should_raise=False,
        )

        try:
            current = await self.client.get_agent(agent_id)
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to retrieve agent {agent_id}: {error}",
                status_label=UPDATE_FAILED_STATUS_LABEL,
            ) from error

        version = current.version
        if not isinstance(version, int):
            raise ActionExecutionError(
                f"Agent {agent_id} returned an unexpected version: {version!r}",
                status_label=UPDATE_FAILED_STATUS_LABEL,
            )

        try:
            agent = await self.client.update_agent(
                agent_id,
                version=version,
                payload=inputs.to_request_payload(),
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to update agent {agent_id}: {error}",
                status_label=UPDATE_FAILED_STATUS_LABEL,
            ) from error

        logger.info(f"Updated Claude agent {agent_id} for run {run.id}")

        await self.register_entity(ObjectKind.AGENT, agent.to_dict(mode="json"), run)

        if isinstance(run, WorkflowNodeRun):
            run.output["agentId"] = agent_id

        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Updated agent {agent_id}",
            status_label=AGENT_UPDATED_STATUS_LABEL,
        )
