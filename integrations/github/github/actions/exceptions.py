import httpx
from github.actions.utils import extract_error_message
from port_ocean.exceptions.execution_manager import ActionExecutionError


class CreatePullRequestError(ActionExecutionError):
    @classmethod
    def from_response(
        cls, response: httpx.Response, prefix: str
    ) -> "CreatePullRequestError":
        return cls(f"{prefix}: {extract_error_message(response)}")


class UpdatePullRequestError(ActionExecutionError):
    @classmethod
    def from_response(
        cls, response: httpx.Response, prefix: str
    ) -> "UpdatePullRequestError":
        return cls(f"{prefix}: {extract_error_message(response)}")


class ClosePullRequestError(ActionExecutionError):
    @classmethod
    def from_response(
        cls, response: httpx.Response, prefix: str
    ) -> "ClosePullRequestError":
        return cls(f"{prefix}: {extract_error_message(response)}")


class MergePullRequestError(ActionExecutionError):
    @classmethod
    def from_response(
        cls, response: httpx.Response, prefix: str
    ) -> "MergePullRequestError":
        return cls(f"{prefix}: {extract_error_message(response)}")


class ReviewPullRequestError(ActionExecutionError):
    @classmethod
    def from_response(
        cls, response: httpx.Response, prefix: str
    ) -> "ReviewPullRequestError":
        return cls(f"{prefix}: {extract_error_message(response)}")
