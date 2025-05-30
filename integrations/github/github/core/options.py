from typing import Required, NotRequired, TypedDict


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: Required[str]


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class ListIssueOptions(TypedDict):
    """Options for listing issues."""

    repo_name: Required[str]
    state: NotRequired[str]


class SingleIssueOptions(TypedDict):
    """Options for fetching a single issue."""

    repo_name: Required[str]
    issue_number: Required[int]
