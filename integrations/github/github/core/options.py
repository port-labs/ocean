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


class ListWorkflowOptions(RepositoryIdentifier):
    """Options for workflows"""


class SingleWorkflowOptions(ListWorkflowOptions):
    workflow_id: Required[str]


class ListWorkflowRunOptions(RepositoryIdentifier):
    """Options for workflow runs"""

    workflow_id: Required[int]
    max_runs: Required[int]


class SingleWorkflowRunOptions(RepositoryIdentifier):
    run_id: Required[str]


class SingleReleaseOptions(RepositoryIdentifier):
    """Options for fetching a single release."""

    release_id: Required[int]


class ListReleaseOptions(RepositoryIdentifier):
    """Options for listing releases."""


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


class SingleEnvironmentOptions(RepositoryIdentifier):
    """Options for fetching a single environment."""

    name: str


class ListEnvironmentsOptions(RepositoryIdentifier):
    """Options for listing environments."""


class SingleDeploymentOptions(RepositoryIdentifier):
    """Options for fetching a single deployment."""

    id: str


class ListDeploymentsOptions(RepositoryIdentifier):
    """Options for listing deployments."""


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

    state: Required[str]
