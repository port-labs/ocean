from port_ocean.context.ocean import ocean

from claude_managed_agents.actions.archive_agent_executor import ArchiveAgentExecutor
from claude_managed_agents.actions.cancel_session_executor import CancelSessionExecutor
from claude_managed_agents.actions.create_agent_executor import CreateAgentExecutor
from claude_managed_agents.actions.create_environment_executor import (
    CreateEnvironmentExecutor,
)
from claude_managed_agents.actions.delete_environment_executor import (
    DeleteEnvironmentExecutor,
)
from claude_managed_agents.actions.trigger_agent_executor import TriggerAgentExecutor
from claude_managed_agents.actions.update_agent_executor import UpdateAgentExecutor
from claude_managed_agents.actions.update_environment_executor import (
    UpdateEnvironmentExecutor,
)


def register_action_executors() -> None:
    """Register all action executors."""
    ocean.register_action_executor(CreateAgentExecutor())
    ocean.register_action_executor(UpdateAgentExecutor())
    ocean.register_action_executor(ArchiveAgentExecutor())
    ocean.register_action_executor(CreateEnvironmentExecutor())
    ocean.register_action_executor(UpdateEnvironmentExecutor())
    ocean.register_action_executor(DeleteEnvironmentExecutor())
    ocean.register_action_executor(TriggerAgentExecutor())
    ocean.register_action_executor(CancelSessionExecutor())
