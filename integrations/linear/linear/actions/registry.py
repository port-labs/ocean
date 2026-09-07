from port_ocean.context.ocean import ocean

from linear.actions.create_issue_executor import CreateIssueExecutor
from linear.actions.create_sub_issue_executor import CreateSubIssueExecutor
from linear.actions.update_issue_executor import UpdateIssueExecutor


def register_actions_executors() -> None:
    """Register Linear action executors."""
    ocean.register_action_executor(CreateIssueExecutor())
    ocean.register_action_executor(CreateSubIssueExecutor())
    ocean.register_action_executor(UpdateIssueExecutor())
