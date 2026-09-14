from port_ocean.context.ocean import ocean

from azure_devops.actions.merge_pull_request_executor import (
    MergePullRequestExecutor,
)
from azure_devops.actions.close_pull_request_executor import (
    ClosePullRequestExecutor,
)
from azure_devops.actions.trigger_pipeline_executor import TriggerPipelineExecutor


def register_actions_executors() -> None:
    """Register all Azure DevOps action executors."""
    ocean.register_action_executor(TriggerPipelineExecutor())
    ocean.register_action_executor(MergePullRequestExecutor())
    ocean.register_action_executor(ClosePullRequestExecutor())
