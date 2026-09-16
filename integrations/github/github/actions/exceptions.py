from typing import Self

import httpx
from github.actions.utils import extract_error_message
from port_ocean.exceptions.execution_manager import ActionExecutionError


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
