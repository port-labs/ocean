from port_ocean.context.ocean import ocean

from actions.create_agent_executor import CreateAgentExecutor
from actions.sync_skill_executor import SyncSkillExecutor
from actions.trigger_agent_executor import TriggerAgentExecutor


def register_action_executors() -> None:
    """Register all action executors."""
    ocean.register_action_executor(CreateAgentExecutor())
    ocean.register_action_executor(SyncSkillExecutor())
    ocean.register_action_executor(TriggerAgentExecutor())
