from typing import TypedDict


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str


class ListPullRequestOptions(TypedDict):
    """Options for listing pull requests."""

    state: str
    repo_name: str


class SinglePullRequestOptions(TypedDict):
    """Options for fetching a single pull request."""

    repo_name: str
    pr_number: int
