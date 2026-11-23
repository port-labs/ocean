from port_ocean.context.ocean import ocean

from factory_ai.actions.execute_droid import ExecuteDroidExecutor


def register_action_executors() -> None:
    """Register all Factory.ai action executors."""
    ocean.register_action_executor(ExecuteDroidExecutor())
