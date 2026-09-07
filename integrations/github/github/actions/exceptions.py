import httpx
from github.actions.utils import extract_error_message
from port_ocean.exceptions.execution_manager import ActionExecutionError


class UpdatePullRequestError(ActionExecutionError):
    DEFAULT_STATUS_LABEL = "Update failed"

    @classmethod
    def from_response(
        cls, response: httpx.Response, prefix: str
    ) -> "UpdatePullRequestError":
        return cls(f"{prefix}: {extract_error_message(response)}")
