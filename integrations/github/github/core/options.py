from typing import NotRequired, Required, TypedDict, List, Optional


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class FileSearchOptions(TypedDict):
    """Options for searching files in repositories."""

    repos: NotRequired[Optional[List[str]]]
    path: Required[str]
    filenames: Required[List[str]]
    skip_parsing: Required[bool]


class FileContentOptions(TypedDict):
    """Options for fetching file content."""

    repo_name: Required[str]
    file_path: Required[str]
    ref: NotRequired[Optional[str]]
