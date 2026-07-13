from port_ocean.context.ocean import ocean
from github.actions.dispatch_workflow_executor import (
    DispatchWorkflowExecutor,
)
from github.actions.external_custom_properties.replace_repositories_external_custom_properties_executor import (
    ReplaceRepositoriesExternalCustomPropertiesExecutor,
)
from github.actions.external_custom_properties.update_repo_external_custom_properties_executor import (
    UpdateRepoExternalCustomPropertiesExecutor,
)


def register_actions_executors() -> None:
    """Register all actions executors."""
    ocean.register_action_executor(DispatchWorkflowExecutor())
    ocean.register_action_executor(UpdateRepoExternalCustomPropertiesExecutor())
    ocean.register_action_executor(
        ReplaceRepositoriesExternalCustomPropertiesExecutor()
    )
