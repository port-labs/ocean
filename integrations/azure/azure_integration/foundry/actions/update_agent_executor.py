from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from azure_integration.foundry.actions.abstract_action_input import (
    AbstractFoundryActionInput,
)
from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.helpers.agent_api import (
    build_update_agent_body,
    definition_kind,
    foundry_features_header,
    latest_agent_definition,
)
from azure_integration.foundry.helpers.utils import deep_merge, enrich_with_project
from azure_integration.foundry.kinds import ObjectKind

UPDATING_STATUS_LABEL = "Updating agent"
UPDATE_FAILED_STATUS_LABEL = "Update failed"
AGENT_UPDATED_STATUS_LABEL = "Agent updated"


class UpdateAgentInputs(AbstractFoundryActionInput):
    agentId: str = Field(min_length=1)
    model: str | None = None
    instructions: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)

    def to_api_body(self) -> dict[str, Any]:
        return build_update_agent_body(
            model=self.model,
            instructions=self.instructions,
            config=self.config or None,
        )


class UpdateAgentExecutor(AbstractFoundryExecutor):
    ACTION_NAME = "update_agent"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = UpdateAgentInputs.from_execution_properties(run.execution_properties)
        patch = inputs.to_api_body()

        if not any(
            (
                inputs.model is not None,
                inputs.instructions is not None,
                bool(inputs.config),
            )
        ):
            raise ActionExecutionError(
                "At least one field must be provided to update",
                status_label=UPDATE_FAILED_STATUS_LABEL,
            )

        await ocean.port_client.post_run_log(
            run,
            f"Updating Foundry agent '{inputs.agentId}'",
            status_label=UPDATING_STATUS_LABEL,
            should_raise=False,
        )

        agent_url = self.client.build_url(
            inputs.projectEndpoint, f"agents/{inputs.agentId}"
        )
        try:
            existing = await self.client.send_api_request(agent_url)
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to update agent: {error}",
                status_label=UPDATE_FAILED_STATUS_LABEL,
            ) from error

        if not isinstance(existing, dict) or not existing:
            raise ActionExecutionError(
                f"Agent '{inputs.agentId}' not found",
                status_label=UPDATE_FAILED_STATUS_LABEL,
            )

        body = deep_merge(
            {"definition": latest_agent_definition(existing) or {"kind": "prompt"}},
            patch,
        )
        definition = body.get("definition")
        if isinstance(definition, dict):
            definition["kind"] = definition.get("kind") or "prompt"

        try:
            agent = await self.client.send_api_request(
                agent_url,
                method="POST",
                json_body=body,
                extra_headers=foundry_features_header(definition_kind(body)),
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to update agent: {error}",
                status_label=UPDATE_FAILED_STATUS_LABEL,
            ) from error

        if not isinstance(agent, dict):
            raise ActionExecutionError(
                "Unexpected update agent response",
                status_label=UPDATE_FAILED_STATUS_LABEL,
            )

        logger.info(f"Updated Foundry agent {inputs.agentId} for run {run.id}")
        await self.register_entity(
            ObjectKind.FOUNDRY_AGENT,
            enrich_with_project(agent, project_endpoint=inputs.projectEndpoint),
            run,
        )
        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Updated agent {inputs.agentId}",
            status_label=AGENT_UPDATED_STATUS_LABEL,
        )
