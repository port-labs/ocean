from typing import TypedDict, NotRequired, Literal, Optional, Required


class PullRequestSelectorOptions(TypedDict):
    """Options for filtering pull requests."""

    user_role: NotRequired[Optional[Literal["member", "contributor", "admin", "owner"]]]
    repo_query: NotRequired[Optional[str]]
    pull_request_query: Required[str]
