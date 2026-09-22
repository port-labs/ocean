from port_ocean.context.ocean import ocean

from jira.actions.change_issue_status_executor import ChangeIssueStatusExecutor
from jira.actions.add_comment_executor import AddCommentExecutor
from jira.actions.create_issue_executor import CreateIssueExecutor
from jira.actions.update_issue_executor import UpdateIssueExecutor


def register_actions_executors() -> None:
    """Register all actions executors."""
    ocean.register_action_executor(CreateIssueExecutor())
    ocean.register_action_executor(UpdateIssueExecutor())
    ocean.register_action_executor(ChangeIssueStatusExecutor())
    ocean.register_action_executor(AddCommentExecutor())
