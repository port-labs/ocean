from typing import TypedDict


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str


class ListWorkflowOptions(TypedDict):
    repo: str


class SingleWorkflowOptions(ListWorkflowOptions):
    resource_id: str
