from typing import Any, Optional
from bitbucket_cloud.webhook_processors.options import PullRequestSelectorOptions
from integration import UserRole


def build_repo_params(
    user_role: Optional[UserRole] = None,
    repo_query: Optional[str] = None,
) -> dict[str, Any]:
    """Build the parameters for the repository filter."""
    params: dict[str, Any] = {}
    if user_role:
        params["role"] = user_role
    if repo_query:
        params["q"] = repo_query.strip()
    return params


def build_pull_request_params(options: PullRequestSelectorOptions) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if options["pull_request_query"]:
        params["q"] = options["pull_request_query"].strip()
    return params
