from typing import Self

import httpx
from github.actions.utils import extract_error_message
from port_ocean.exceptions.execution_manager import ActionExecutionError


class IssueActionError(ActionExecutionError):
    @classmethod
    def from_response(cls, response: httpx.Response, prefix: str) -> Self:
        return cls(f"{prefix}: {extract_error_message(response)}")


class CreateIssueError(IssueActionError):
    DEFAULT_STATUS_LABEL = "Create failed"


class EditIssueError(IssueActionError):
    DEFAULT_STATUS_LABEL = "Edit failed"


class CloseIssueError(IssueActionError):
    DEFAULT_STATUS_LABEL = "Close failed"


class PullRequestActionError(ActionExecutionError):
    @classmethod
    def from_response(cls, response: httpx.Response, prefix: str) -> Self:
        return cls(f"{prefix}: {extract_error_message(response)}")


class CreatePullRequestError(PullRequestActionError):
    DEFAULT_STATUS_LABEL = "Create failed"


class UpdatePullRequestError(PullRequestActionError):
    DEFAULT_STATUS_LABEL = "Update failed"


class ClosePullRequestError(PullRequestActionError):
    DEFAULT_STATUS_LABEL = "Close failed"


class MergePullRequestError(PullRequestActionError):
    DEFAULT_STATUS_LABEL = "Merge failed"


class ReviewPullRequestError(PullRequestActionError):
    DEFAULT_STATUS_LABEL = "Review failed"


class CommentActionError(ActionExecutionError):
    @classmethod
    def from_response(cls, response: httpx.Response, prefix: str) -> Self:
        return cls(f"{prefix}: {extract_error_message(response)}")


class CreateCommentError(CommentActionError):
    DEFAULT_STATUS_LABEL = "Create failed"


class EditCommentError(CommentActionError):
    DEFAULT_STATUS_LABEL = "Edit failed"


class DeleteCommentError(CommentActionError):
    DEFAULT_STATUS_LABEL = "Delete failed"
