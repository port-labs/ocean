from port_ocean.context.ocean import ocean
from github.actions.close_pull_request_executor import ClosePullRequestExecutor
from github.actions.create_pull_request_executor import CreatePullRequestExecutor
from github.actions.dispatch_workflow_executor import (
    DispatchWorkflowExecutor,
)
from github.actions.merge_pull_request_executor import MergePullRequestExecutor
from github.actions.review_pull_request_executor import ReviewPullRequestExecutor
from github.actions.update_pull_request_executor import UpdatePullRequestExecutor
from github.actions.external_custom_properties.bulk_delete_external_custom_property_values_executor import (
    BulkDeleteExternalCustomPropertyValuesExecutor,
)
from github.actions.external_custom_properties.bulk_update_external_custom_property_values_executor import (
    BulkUpdateExternalCustomPropertyValuesExecutor,
)
from github.actions.external_custom_properties.update_repo_external_custom_properties_executor import (
    UpdateRepoExternalCustomPropertiesExecutor,
)


def register_actions_executors() -> None:
    """Register all actions executors."""
    ocean.register_action_executor(DispatchWorkflowExecutor())
    ocean.register_action_executor(UpdateRepoExternalCustomPropertiesExecutor())
    ocean.register_action_executor(BulkUpdateExternalCustomPropertyValuesExecutor())
    ocean.register_action_executor(BulkDeleteExternalCustomPropertyValuesExecutor())
    ocean.register_action_executor(CreatePullRequestExecutor())
    ocean.register_action_executor(UpdatePullRequestExecutor())
    ocean.register_action_executor(ClosePullRequestExecutor())
    ocean.register_action_executor(MergePullRequestExecutor())
    ocean.register_action_executor(ReviewPullRequestExecutor())
