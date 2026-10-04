from port_ocean.core.models import IntegrationRun, WorkflowNodeRun

from linear.core.mutations.document.types import MutationDocument
from linear.core.mutations.issue.types import (
    MutationComment,
    MutationIssue,
    MutationReaction,
)


def set_issue_run_output(run: IntegrationRun, issue: MutationIssue) -> None:
    if isinstance(run, WorkflowNodeRun):
        run.output = {
            "identifier": issue.identifier,
            "issueId": issue.id,
            "issueUrl": issue.url,
        }


def set_document_run_output(run: IntegrationRun, document: MutationDocument) -> None:
    if isinstance(run, WorkflowNodeRun):
        run.output = {
            "documentId": document.id,
            "documentUrl": document.url,
            "title": document.title,
        }


def set_comment_run_output(
    run: IntegrationRun, issue_id: str, comment: MutationComment
) -> None:
    if isinstance(run, WorkflowNodeRun):
        run.output = {
            "commentId": comment.id,
            "issueId": issue_id,
            "body": comment.body,
        }


def set_reaction_run_output(
    run: IntegrationRun, issue_id: str, reaction: MutationReaction
) -> None:
    if isinstance(run, WorkflowNodeRun):
        run.output = {
            "reactionId": reaction.id,
            "issueId": issue_id,
            "emoji": reaction.emoji,
        }


def set_issue_id_run_output(run: IntegrationRun, issue_id: str) -> None:
    if isinstance(run, WorkflowNodeRun):
        run.output = {"issueId": issue_id}
