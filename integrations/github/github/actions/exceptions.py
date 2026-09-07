import httpx
from github.actions.utils import extract_error_message
from port_ocean.exceptions.execution_manager import ActionExecutionError


class CreatePullRequestError(ActionExecutionError):
    DEFAULT_STATUS_LABEL = "Creation failed"

    @classmethod
    def from_response(
        cls, response: httpx.Response, prefix: str
    ) -> "CreatePullRequestError":
        return cls(f"{prefix}: {extract_error_message(response)}")
