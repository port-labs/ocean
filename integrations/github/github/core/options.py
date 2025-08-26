from typing import List, NotRequired, Optional, Required, TypedDict


class SingleRepositoryOptions(TypedDict):
    name: str
    included_relationships: NotRequired[Optional[List[str]]]


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str
    included_relationships: NotRequired[Optional[List[str]]]


class SingleFolderOptions(TypedDict):
    repo: str
    path: str


class ListFolderOptions(TypedDict):
    repo_mapping: Required[dict[str, dict[str, list[str]]]]


class RepositoryIdentifier(TypedDict):
    """Options for identifying a repository."""

    repo_name: Required[str]


class SinglePullRequestOptions(RepositoryIdentifier):
    """Options for fetching a single pull request."""

    pr_number: Required[int]


class ListPullRequestOptions(RepositoryIdentifier):
    """Options for listing pull requests."""

    states: Required[list[str]]
    max_results: Required[int]
    since: Required[int]


class SingleIssueOptions(RepositoryIdentifier):
    """Options for fetching a single issue."""

    issue_number: Required[int]


class ListIssueOptions(RepositoryIdentifier):
    """Options for listing issues."""

    state: Required[str]


class SingleUserOptions(TypedDict):
    login: Required[str]


class SingleTeamOptions(TypedDict):
    slug: Required[str]


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


class FileContentOptions(TypedDict):
    """Options for fetching file content."""

    repo_name: Required[str]
    file_path: Required[str]
    branch: NotRequired[Optional[str]]


class FileSearchOptions(TypedDict):
    """Options for searching files in repositories."""

    path: Required[str]
    skip_parsing: Required[bool]
    branch: NotRequired[Optional[str]]


class ListFileSearchOptions(TypedDict):
    """Map of repository names to file search options."""

    repo_name: Required[str]
    files: Required[List[FileSearchOptions]]


class SingleCollaboratorOptions(RepositoryIdentifier):
    """Options for fetching a single collaborator."""

    username: Required[str]


class ListCollaboratorOptions(RepositoryIdentifier):
    """Options for listing collaborators."""
