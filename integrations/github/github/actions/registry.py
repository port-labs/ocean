from port_ocean.context.ocean import ocean
from github.actions.dispatch_workflow_executor import (
    DispatchWorkflowExecutor,
)


def register_actions_executors() -> None:
    """Register all actions executors."""
    ocean.register_action_executor(DispatchWorkflowExecutor())
