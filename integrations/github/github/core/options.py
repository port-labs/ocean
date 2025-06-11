from typing import Required, TypedDict


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

    state: Required[str]


class SingleIssueOptions(RepositoryIdentifier):
    """Options for fetching a single issue."""

    issue_number: Required[int]


class ListIssueOptions(RepositoryIdentifier):
    """Options for listing issues."""

    state: Required[str]

class SingleReleaseOptions(RepositoryIdentifier):
    """Options for fetching a single release."""

    release_id: Required[int]


class ListReleaseOptions(RepositoryIdentifier):
    """Options for listing releases."""

    repo_name: Required[str]


class SingleTagOptions(RepositoryIdentifier):
    """Options for fetching a single tag."""

    tag_name: Required[str]


class ListTagOptions(RepositoryIdentifier):
    """Options for listing tags."""


class SingleBranchOptions(RepositoryIdentifier):
    """Options for fetching a single branch."""

    branch_name: Required[str]


class ListBranchOptions(RepositoryIdentifier):
    """Options for listing branches."""
