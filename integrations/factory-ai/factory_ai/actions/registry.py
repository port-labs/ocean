from port_ocean.context.ocean import ocean

from factory_ai.actions.execute_droid import ExecuteDroidExecutor
from factory_ai.actions.interrupt_session import InterruptSessionExecutor


def register_action_executors() -> None:
    """Register all Factory.ai action executors."""
    ocean.register_action_executor(ExecuteDroidExecutor())
    ocean.register_action_executor(InterruptSessionExecutor())
