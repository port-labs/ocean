from typing import Literal, NotRequired, TypedDict, Optional


class IssueOptions(TypedDict):
    """Options for fetching issues."""

    issue_type: NotRequired[Optional[Literal["issue", "incident", "test_case", "task"]]]
    labels: NotRequired[Optional[str]]
    non_archived: NotRequired[Optional[bool]]
    state: NotRequired[Optional[Literal["opened", "closed"]]]
    updated_after: NotRequired[Optional[str]]
