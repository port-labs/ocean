from typing import TypedDict


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str


class ListWorkflowOptions(TypedDict):
    repo: str


class SingleWorkflowOptions(ListWorkflowOptions):
    resource_id: str
