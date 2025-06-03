from typing import TypedDict, List, Optional


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class FileSearchOptions(TypedDict):
    """Options for searching files in repositories."""
    
    repos: Optional[List[str]]
    path: str
    filenames: List[str]
    skip_parsing: bool


class SingleFileOptions(TypedDict):
    """Options for fetching a single file."""
    
    repo_name: str
    ref: str
    file_path: str
    skip_parsing: bool
