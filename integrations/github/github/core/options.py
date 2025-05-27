from typing import TypedDict


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class SingleUserOptions(TypedDict):
    login: str


class SingleTeamOptions(TypedDict):
    slug: str
