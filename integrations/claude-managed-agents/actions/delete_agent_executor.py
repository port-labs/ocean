from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun, WorkflowNodeRun
from port_ocean.exceptions.execution_manager import ActionExecutionError
from pydantic import Field

from actions.abstract_action_input import AbstractAnthropicActionInput
from actions.abstract_executor import AbstractAnthropicExecutor
from integration import ObjectKind

ARCHIVING_STATUS_LABEL = "Archiving agent"
ARCHIVE_FAILED_STATUS_LABEL = "Archive failed"
AGENT_ARCHIVED_STATUS_LABEL = "Agent archived"

# The Anthropic Managed Agents API has no delete endpoint for agents; archive
# is the terminal (permanent) operation — it makes the agent read-only and
# prevents new sessions from referencing it. Existing sessions continue.
# This action is therefore named `delete_agent` from Port's perspective but
# maps to the SDK's `beta.agents.archive` under the hood.


class DeleteAgentInputs(AbstractAnthropicActionInput):
    agentId: str = Field(min_length=1)


class DeleteAgentExecutor(AbstractAnthropicExecutor):
    """Executor for the `delete_agent` action.

    Archives a Claude managed agent, making it permanently read-only. The
    Anthropic API has no hard-delete for agents — archive is the closest
    terminal operation. The run completes synchronously: no async webhook is
    involved.

    Runs are serialized per agent id so two concurrent archive attempts on the
    same agent do not race each other.
    """

    ACTION_NAME = "delete_agent"

    async def _get_partition_key(self, run: IntegrationRun) -> str | None:
        return run.execution_properties.get("agentId")

    async def execute(self, run: IntegrationRun) -> None:
        inputs = DeleteAgentInputs.from_execution_properties(run.execution_properties)
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

        # Reflect the archived state in the catalog so the entity is updated
        # without waiting for the next resync. Agents have no webhook events,
        # so the entity would otherwise remain stale until then. Best-effort:
        # never fails the run.
        await self.register_entity(ObjectKind.AGENT, agent, run)

        if isinstance(run, WorkflowNodeRun):
            run.output["agentId"] = agent_id

        await ocean.port_client.report_run_completed(
            run,
            True,
            f"Archived agent {agent_id}",
            status_label=AGENT_ARCHIVED_STATUS_LABEL,
        )
