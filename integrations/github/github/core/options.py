from typing import TypedDict


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class ListIssueOptions(TypedDict):
    """Options for listing issues."""

    repo_name: str
    state: str


class SingleIssueOptions(TypedDict):
    """Options for fetching a single issue."""

    repo_name: str
    issue_number: int
