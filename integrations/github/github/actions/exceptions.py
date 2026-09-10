import httpx
from github.actions.utils import extract_error_message
from port_ocean.exceptions.execution_manager import ActionExecutionError


class PullRequestCommentError(ActionExecutionError):
    @classmethod
    def from_response(
        cls, response: httpx.Response, prefix: str
    ) -> "PullRequestCommentError":
        return cls(f"{prefix}: {extract_error_message(response)}")
