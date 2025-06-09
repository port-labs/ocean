from typing import TypedDict


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class ListWorkflowOptions(TypedDict):
    repo: str


class SingleWorkflowOptions(ListWorkflowOptions):
    resource_id: str


class ListWorkflowRunOptions(TypedDict):
    repo: str


class SingleWorkflowRunOptions(ListWorkflowOptions):
    resource_id: str
