from typing import TypedDict


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class RepoOptions(TypedDict):
    """Base options requiring a repository name."""

    repo: str


class SingleRepoResourceOptions(RepoOptions):
    """Base options requiring a repository and a resource ID."""

    resource_id: str


class ListWorkflowOptions(RepoOptions):
    """Options for listing workflows within a repository."""


class SingleWorkflowOptions(SingleRepoResourceOptions):
    """Options for fetching a single workflow within a repository."""


class ListWorkflowRunOptions(RepoOptions):
    """Options for listing workflow runs within a repository."""


class SingleWorkflowRunOptions(SingleRepoResourceOptions):
    """Options for fetching a single workflow run within a repository."""
