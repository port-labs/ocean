from typing import Required, TypedDict


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class SingleUserOptions(TypedDict):
    login: Required[str]


class SingleTeamOptions(TypedDict):
    slug: Required[str]
