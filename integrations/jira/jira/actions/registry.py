from port_ocean.context.ocean import ocean

from jira.actions.change_issue_status_executor import ChangeIssueStatusExecutor
from jira.actions.create_issue_executor import CreateIssueExecutor


def register_actions_executors() -> None:
    """Register all actions executors."""
    ocean.register_action_executor(CreateIssueExecutor())
    ocean.register_action_executor(ChangeIssueStatusExecutor())
