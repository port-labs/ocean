from port_ocean.context.ocean import ocean
from integrations.github.github.actions.dispatch_workflow_executor import (
    DispatchWorkflowExecutor,
)


def register_actions_executors():
    """Register all actions executors."""
    ocean.register_action_executor(DispatchWorkflowExecutor(ocean.port_client))
