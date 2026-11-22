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
from azure_integration.foundry.core.exporters.agents_exporter import AgentsExporter
from azure_integration.foundry.core.options import SingleAgentOptions
from azure_integration.foundry.helpers.utils import (
    deep_merge,
    enrich_with_project,
    project_name_from_endpoint,
)
from azure_integration.foundry.kinds import ObjectKind
from azure_integration.foundry.models.agent import Agent, parse_agent_definition

UPDATING_STATUS_LABEL = "Updating agent"
UPDATE_FAILED_STATUS_LABEL = "Update failed"
AGENT_UPDATED_STATUS_LABEL = "Agent updated"


class UpdateAgentInputs(AbstractFoundryActionInput):
    agentId: str = Field(min_length=1)
    model: str | None = None
    instructions: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)

    def to_api_body(self) -> dict[str, Any]:
        # Partial patch; executor merges over GET before POST.
        body = deep_merge({}, self.config)
        definition = body.get("definition")
        if not isinstance(definition, dict):
            definition = {}
            body["definition"] = definition

        kind = definition.get("kind")
        if kind in (None, "prompt"):
            if self.model is not None:
                definition["model"] = self.model
            if self.instructions is not None:
                definition["instructions"] = self.instructions
        return body


class UpdateAgentExecutor(AbstractFoundryExecutor):
    ACTION_NAME = "update_agent"

    async def execute(self, run: IntegrationRun) -> None:
        inputs = UpdateAgentInputs.from_execution_properties(run.execution_properties)

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

        patch = inputs.to_api_body()

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
            existing = await AgentsExporter(self.client).get_resource(
                SingleAgentOptions(
                    project_endpoint=inputs.projectEndpoint,
                    project_id=project_name_from_endpoint(inputs.projectEndpoint),
                    agent_id=inputs.agentId,
                )
            )
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to update agent: {error}",
                status_label=UPDATE_FAILED_STATUS_LABEL,
            ) from error

        if existing is None:
            raise ActionExecutionError(
                f"Agent '{inputs.agentId}' not found",
                status_label=UPDATE_FAILED_STATUS_LABEL,
            )

        base = Agent.model_validate(existing).latest_definition.model_dump()
        body = deep_merge(
            {"definition": base or {"kind": "prompt"}},
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
                extra_headers=parse_agent_definition(
                    body["definition"]
                ).features_header,
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
