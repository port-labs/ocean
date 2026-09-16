from typing import Self

import httpx
from github.actions.utils import extract_error_message
from port_ocean.exceptions.execution_manager import ActionExecutionError


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
