from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from claude_managed_agents.actions.abstract_action_input import (
    AbstractAnthropicActionInput,
)
from claude_managed_agents.actions.abstract_executor import AbstractAnthropicExecutor
from claude_managed_agents.integration import AgentResourceConfig, ObjectKind

ARCHIVING_STATUS_LABEL = "Archiving agent"
ARCHIVE_FAILED_STATUS_LABEL = "Archive failed"
AGENT_ARCHIVED_STATUS_LABEL = "Agent archived"


class ArchiveAgentInputs(AbstractAnthropicActionInput):
    agentId: str = Field(min_length=1)


class ArchiveAgentExecutor(AbstractAnthropicExecutor):
    """Executor for the `archive_agent` action.

    Archives a Claude managed agent, making it permanently read-only. Archive
    is the terminal operation on the Anthropic API — no hard-delete exists.
    Existing sessions continue; new sessions cannot reference the agent.
    The run completes synchronously: no async webhook is involved.

    Runs are serialized per agent id so two concurrent archive attempts on the
    same agent do not race each other.
    """

    ACTION_NAME = "archive_agent"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return run.execution_properties.get("agentId")

    async def _should_keep_archived_agents(self) -> bool:
        """Whether any `agent` mapping has `includeArchived` on. Defaults to
        keeping the agent when the config cannot be read, so a failure here
        never drops an entity."""
        try:
            port_app_config = (
                await ocean.integration.port_app_config_handler.get_port_app_config(
                    use_cache=False
                )
            )
        except Exception as error:
            logger.warning(
                f"Could not read the port app config to check includeArchived: {error}"
            )
            return True

        agent_selectors = [
            resource.selector
            for resource in port_app_config.resources
            if isinstance(resource, AgentResourceConfig)
        ]
        return not agent_selectors or any(
            selector.include_archived for selector in agent_selectors
        )

    async def execute(self, run: IntegrationRun) -> None:
        inputs = ArchiveAgentInputs.from_execution_properties(run.execution_properties)
        agent_id = inputs.agentId

        await ocean.port_client.post_run_log(
            run,
            f"Archiving Claude agent {agent_id}",
            status_label=ARCHIVING_STATUS_LABEL,
            should_raise=False,
        )

        try:
            agent = await self.client.archive_agent(agent_id)
        except Exception as error:
            raise ActionExecutionError(
                f"Failed to archive agent {agent_id}: {error}",
                status_label=ARCHIVE_FAILED_STATUS_LABEL,
            ) from error

        logger.info(f"Archived Claude agent {agent_id} for run {run.id}")

        # Reflect the archived state in the catalog immediately (webhooks also
        # keep agents in sync). Best-effort: never fails the run.
        raw_agent = agent.to_dict(mode="json", warnings=False)
        if await self._should_keep_archived_agents():
            await self.register_entity(ObjectKind.AGENT, raw_agent, run)
        else:
            await self.unregister_entity(ObjectKind.AGENT, raw_agent, run)

        if isinstance(run, WorkflowNodeRun):
            run.output["agentId"] = agent_id

        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Archived agent {agent_id}",
            status_label=AGENT_ARCHIVED_STATUS_LABEL,
        )
