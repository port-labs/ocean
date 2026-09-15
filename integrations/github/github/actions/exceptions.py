import httpx
from github.actions.utils import extract_error_message
from port_ocean.exceptions.execution_manager import ActionExecutionError


class PullRequestActionError(ActionExecutionError):
    @classmethod
    def from_response(
        cls, response: httpx.Response, prefix: str
    ) -> "PullRequestActionError":
        return cls(f"{prefix}: {extract_error_message(response)}")
