from port_ocean.context.ocean import ocean

from linear.actions.add_comment_executor import AddCommentExecutor
from linear.actions.add_document_executor import AddDocumentExecutor
from linear.actions.change_status_executor import ChangeStatusExecutor
from linear.actions.create_issue_executor import CreateIssueExecutor
from linear.actions.create_sub_issue_executor import CreateSubIssueExecutor
from linear.actions.update_issue_executor import UpdateIssueExecutor


def register_actions_executors() -> None:
    """Register Linear action executors."""
    ocean.register_action_executor(CreateIssueExecutor())
    ocean.register_action_executor(CreateSubIssueExecutor())
    ocean.register_action_executor(UpdateIssueExecutor())
    ocean.register_action_executor(ChangeStatusExecutor())
    ocean.register_action_executor(AddCommentExecutor())
    ocean.register_action_executor(AddDocumentExecutor())
