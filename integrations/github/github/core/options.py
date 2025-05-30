from typing import NotRequired, Required, TypedDict


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class SinglePullRequestOptions(TypedDict):
    """Options for fetching a single pull request."""

    repo_name: Required[str]
    pr_number: Required[int]


class ListPullRequestOptions(TypedDict):
    """Options for listing pull requests."""

    repo_name: Required[str]
    state: NotRequired[str]
