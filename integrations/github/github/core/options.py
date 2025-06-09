from typing import Required, TypedDict


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class ListWorkflowOptions(TypedDict):
    repo: Required[str]


class SingleWorkflowOptions(ListWorkflowOptions):
    resource_id: Required[str]


class ListWorkflowRunOptions(TypedDict):
    repo: Required[str]


class SingleWorkflowRunOptions(ListWorkflowOptions):
    resource_id: Required[str]
