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


class SingleDependabotAlertOptions(RepositoryIdentifier):
    """Options for fetching a single Dependabot alert."""

    alert_number: Required[str]


class ListDependabotAlertOptions(RepositoryIdentifier):
    """Options for listing Dependabot alerts."""

    state: Required[list[str]]


class SingleCodeScanningAlertOptions(RepositoryIdentifier):
    """Options for fetching a single code scanning alert."""

    alert_number: Required[str]


class ListCodeScanningAlertOptions(RepositoryIdentifier):
    """Options for listing code scanning alerts."""

    state: Required[list[str]]
