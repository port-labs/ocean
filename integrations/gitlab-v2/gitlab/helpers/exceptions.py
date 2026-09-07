import json

import httpx


class MissingExecutionPropertyError(Exception):
    """Raised when a required execution property is absent from the action run."""


def _response_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except Exception:
        body = None

    if isinstance(body, dict):
        for key in ("error_description", "message", "error"):
            if (value := body.get(key)) is not None:
                return value if isinstance(value, str) else json.dumps(value)

    text = response.text.strip()
    return text or f"HTTP {response.status_code}"


class GitlabTriggerPipelineError(Exception):
    """Raised when the GitLab API returns an error while triggering a pipeline."""

    @classmethod
    def from_response(
        cls, response: httpx.Response, prefix: str
    ) -> "GitlabTriggerPipelineError":
        return cls(f"{prefix}: {_response_detail(response)}")


class GitlabCreateMergeRequestError(Exception):
    """Raised when the GitLab API returns an error while creating a merge request."""

    @classmethod
    def from_response(
        cls, response: httpx.Response, prefix: str
    ) -> "GitlabCreateMergeRequestError":
        return cls(f"{prefix}: {_response_detail(response)}")
