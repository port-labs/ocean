from port_ocean.context.ocean import ocean

from azure_devops.actions.create_pull_request_executor import (
    CreatePullRequestExecutor,
)
from azure_devops.actions.merge_pull_request_executor import (
    MergePullRequestExecutor,
)
from azure_devops.actions.close_pull_request_executor import (
    ClosePullRequestExecutor,
)
from azure_devops.actions.create_pull_request_thread_executor import (
    CreatePullRequestThreadExecutor,
)
from azure_devops.actions.trigger_pipeline_executor import TriggerPipelineExecutor
from azure_devops.actions.update_pull_request_executor import UpdatePullRequestExecutor
from azure_devops.actions.update_pull_request_labels_executor import (
    UpdatePullRequestLabelsExecutor,
)


def register_actions_executors() -> None:
    """Register all Azure DevOps action executors."""
    ocean.register_action_executor(ClosePullRequestExecutor())
    ocean.register_action_executor(CreatePullRequestThreadExecutor())
    ocean.register_action_executor(CreatePullRequestExecutor())
    ocean.register_action_executor(MergePullRequestExecutor())
    ocean.register_action_executor(TriggerPipelineExecutor())
    ocean.register_action_executor(UpdatePullRequestExecutor())
    ocean.register_action_executor(UpdatePullRequestLabelsExecutor())
