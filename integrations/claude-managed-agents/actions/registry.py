from port_ocean.context.ocean import ocean

from actions.archive_agent_executor import ArchiveAgentExecutor
from actions.cancel_session_executor import CancelSessionExecutor
from actions.create_agent_executor import CreateAgentExecutor
from actions.trigger_agent_executor import TriggerAgentExecutor
from actions.update_agent_executor import UpdateAgentExecutor


def register_action_executors() -> None:
    """Register all action executors."""
    ocean.register_action_executor(CreateAgentExecutor())
    ocean.register_action_executor(UpdateAgentExecutor())
    ocean.register_action_executor(TriggerAgentExecutor())
    ocean.register_action_executor(CancelSessionExecutor())
    ocean.register_action_executor(ArchiveAgentExecutor())
