from typing import TypedDict, Required, NotRequired, Literal, Optional


class PullRequestSelectorOptions(TypedDict):
    """Options for filtering pull requests."""

    states: Required[list[Literal["OPEN", "MERGED", "DECLINED", "SUPERSEDED"]]]
    user_role: NotRequired[Optional[Literal["member", "contributor", "admin", "owner"]]]
    repo_query: NotRequired[Optional[str]]
    max_results: Required[int]
