from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field, field_validator, model_validator

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

    @field_validator("enablePortMcp", mode="before")
    @classmethod
    def _coerce_enable_port_mcp(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.lower() in {"true", "1", "yes"}
        return value

    @model_validator(mode="after")
    def at_least_one_update_field(self) -> "UpdateAgentInputs":
        if not any(
            [
                self.name,
                self.model,
                self.systemPrompt,
                self.config,
                self.enablePortMcp is True,
            ]
        ):
            raise ValueError(
                "at least one of name, model, systemPrompt, config, or "
                "enablePortMcp=true must be provided"
            )
        return self

    def to_request_payload(self) -> dict[str, Any]:
        payload = self.model_dump(
            exclude={"agentId", "config", "enablePortMcp"}, exclude_none=True
        )
        if "systemPrompt" in payload:
            payload["system"] = payload.pop("systemPrompt")

        return {**payload, **(self.config or {})}

    def with_port_mcp(self, payload: dict[str, Any], current: Any) -> dict[str, Any]:
        if self.enablePortMcp is not True:
            return payload
        config = dict(self.config or {})
        for key, current_value in (
            ("tools", getattr(current, "tools", None)),
            ("mcp_servers", getattr(current, "mcp_servers", None)),
        ):
            if key not in config:
                config[key] = _as_dicts(current_value)
        metadata = getattr(current, "metadata", None)
        if "metadata" not in config and isinstance(metadata, dict):
            config["metadata"] = dict(metadata)
        return {**payload, **apply_port_mcp_to_agent_config(config)}


def _as_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            items.append(dict(item))
        elif hasattr(item, "model_dump"):
            dumped = item.model_dump(mode="json", exclude_none=True)
            if isinstance(dumped, dict):
                items.append(dumped)
    return items


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
                payload=inputs.with_port_mcp(inputs.to_request_payload(), current),
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
