from typing import Required, TypedDict


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class SingleFolderOptions(TypedDict):
    repo: str
    path: str


class ListFolderOptions(TypedDict):
    repo: Required[dict]
    path: Required[str]
    branch: Required[str]
