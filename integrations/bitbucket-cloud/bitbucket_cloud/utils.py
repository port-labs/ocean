from typing import Any, Optional, Literal


def build_repo_params(
    user_role: Optional[Literal["member", "contributor", "admin", "owner"]] = None,
    repo_query: Optional[str] = None,
) -> dict[str, Any]:
    """Build the parameters for the repository filter."""
    params: dict[str, Any] = {}
    if user_role:
        params["role"] = user_role
    if repo_query:
        params["q"] = repo_query.strip()
    return params
