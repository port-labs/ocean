from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.actions.utils import get_run_access_token
from port_ocean.core.models import IntegrationRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from azure_integration.foundry.actions.abstract_action_input import (
    AbstractFoundryActionInput,
)
from azure_integration.foundry.actions.abstract_executor import AbstractFoundryExecutor
from azure_integration.foundry.helpers.agent_api import (
    definition_kind,
    foundry_features_header,
    latest_agent_definition,
)
from azure_integration.foundry.helpers.port_mcp import (
    TOOLBOX_SERVER_LABEL,
    attach_toolbox_to_agent_config,
    ensure_ootb_mcp,
    fetch_agent_tools,
    sanitize_git_provider,
    toolbox_consumer_url,
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
    enablePortMcp: bool | None = None
    gitAccessToken: str | None = Field(default=None, min_length=1)
    gitProvider: str = Field(default="github")
    toolboxName: str | None = Field(default=None, min_length=1)

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
        git_provider = sanitize_git_provider(inputs.gitProvider)

        if not any(
            (
                inputs.model is not None,
                inputs.instructions is not None,
                bool(inputs.config),
                inputs.enablePortMcp is not None,
                inputs.gitAccessToken is not None,
            )
        ):
            raise ActionExecutionError(
                "At least one field must be provided to update",
                status_label=UPDATE_FAILED_STATUS_LABEL,
            )

        patch = inputs.to_api_body()

        if inputs.enablePortMcp is not None or inputs.gitAccessToken is not None:
            existing_tools = await fetch_agent_tools(
                self.client,
                project_endpoint=inputs.projectEndpoint,
                agent_id=inputs.agentId,
            )
            enable_port = inputs.enablePortMcp is True
            had_ootb_toolbox = any(
                isinstance(t, dict) and t.get("server_label") == TOOLBOX_SERVER_LABEL
                for t in existing_tools
            )
            if enable_port and not get_run_access_token(run):
                logger.warning(
                    f"enablePortMcp set for update on agent {inputs.agentId} but "
                    "no execution identity token; Port connection will not be reminted"
                )
            try:
                toolbox_result = await ensure_ootb_mcp(
                    self.client,
                    project_endpoint=inputs.projectEndpoint,
                    agent_id=inputs.agentId,
                    enable_port_mcp=enable_port,
                    port_access_token=(
                        get_run_access_token(run) if enable_port else None
                    ),
                    git_access_token=inputs.gitAccessToken,
                    git_provider=git_provider,
                    attach_to_prompt_agent=False,
                    existing_tools=existing_tools,
                    include_existing_port_in_toolbox=(
                        inputs.enablePortMcp is None
                        and bool(inputs.gitAccessToken)
                        and had_ootb_toolbox
                    ),
                    toolbox_name=inputs.toolboxName,
                )
            except Exception as error:
                raise ActionExecutionError(
                    f"Failed to prepare ootb MCP toolbox: {error}",
                    status_label=UPDATE_FAILED_STATUS_LABEL,
                ) from error

            if inputs.enablePortMcp is False:
                toolbox_url: str | None = None
            elif toolbox_result:
                toolbox_name, toolbox_version = toolbox_result
                toolbox_url = toolbox_consumer_url(
                    inputs.projectEndpoint,
                    toolbox_name,
                    version=toolbox_version,
                )
            else:
                toolbox_url = next(
                    (
                        t.get("server_url")
                        for t in existing_tools
                        if isinstance(t, dict)
                        and t.get("server_label") == TOOLBOX_SERVER_LABEL
                    ),
                    None,
                )
            patch = attach_toolbox_to_agent_config(
                patch,
                toolbox_url=toolbox_url,
                existing_tools=existing_tools,
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
