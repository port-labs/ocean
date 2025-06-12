from typing import List, NotRequired, Optional, Required, TypedDict


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


class FileSearchOptions(TypedDict):
    """Options for searching files in repositories."""

    repos: NotRequired[Optional[List[str]]]
    path: Required[str]
    filenames: Required[List[str]]
    skip_parsing: Required[bool]
    branch: Required[str]


class FileContentOptions(TypedDict):
    """Options for fetching file content."""

    repo_name: Required[str]
    file_path: Required[str]
    branch: Required[str]