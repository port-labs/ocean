from typing import Required, TypedDict


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class SingleReleaseOptions(TypedDict):
    """Options for fetching a single release."""

    repo_name: Required[str]
    release_id: Required[int]


class ListReleaseOptions(TypedDict):
    """Options for listing releases."""

    repo_name: Required[str]


class SingleTagOptions(TypedDict):
    """Options for fetching a single tag."""

    repo_name: Required[str]
    tag_name: Required[str]


class ListTagOptions(TypedDict):
    """Options for listing tags."""

    repo_name: Required[str]


class SingleBranchOptions(TypedDict):
    """Options for fetching a single branch."""

    repo_name: Required[str]
    branch_name: Required[str]


class ListBranchOptions(TypedDict):
    """Options for listing branches."""

    repo_name: Required[str]
