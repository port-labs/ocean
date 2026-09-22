from port_ocean.context.ocean import ocean

from jira.actions.create_issue_executor import CreateIssueExecutor
from jira.actions.update_issue_executor import UpdateIssueExecutor


def register_actions_executors() -> None:
    """Register all actions executors."""
    ocean.register_action_executor(CreateIssueExecutor())
    ocean.register_action_executor(UpdateIssueExecutor())
