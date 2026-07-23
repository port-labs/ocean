from port_ocean.context.ocean import ocean

from azure_devops.actions.trigger_pipeline_executor import TriggerPipelineExecutor


def register_actions_executors() -> None:
    """Register all Azure DevOps action executors."""
    ocean.register_action_executor(TriggerPipelineExecutor())
