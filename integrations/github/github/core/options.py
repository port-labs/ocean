from datetime import datetime
from typing import NotRequired, Optional, Required, TypedDict


class SingleRepositoryOptions(TypedDict):
    name: str


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class RepositoryIdentifier(TypedDict):
    """Options for identifying a repository."""

    repo_name: Required[str]


class SinglePullRequestOptions(RepositoryIdentifier):
    """Options for fetching a single pull request."""

    pr_number: Required[int]


class ListPullRequestOptions(RepositoryIdentifier):
    """Options for listing pull requests."""

    state: NotRequired[str]
    start_time: NotRequired[Optional[datetime]]
    end_time: NotRequired[Optional[datetime]]
