from typing import Any, Dict, Optional, TypedDict


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single repository."""

    name: str


class ListRepositoryOptions(TypedDict):
    """Options for listing repositories."""

    type: str


class SingleDependabotAlertOptions(TypedDict):
    """Options for fetching a single Dependabot alert."""

    repo_name: str
    alert_number: str


class ListDependabotAlertOptions(TypedDict):
    """Options for listing Dependabot alerts."""

    repo_name: str
    state: list[str]

class SingleCodeScanningAlertOptions(TypedDict):
    """Options for fetching a single code scanning alert."""

    repo_name: str
    alert_number: str

class ListCodeScanningAlertOptions(TypedDict):
    """Options for listing code scanning alerts."""

    repo_name: str
    state: list[str]

class SingleReleaseOptions(TypedDict):
    """Options for fetching a single release."""

    repo_name: str
    release_name: str

class ListReleaseOptions(TypedDict):
    """Options for listing releases."""
    repo_name: str


class SingleTagOptions(TypedDict):
    """Options for fetching a single tag."""

    repo_name: str
    tag_name: str
    
class ListTagOptions(TypedDict):
    """Options for listing tags."""

    repo_name: str

class SingleBranchOptions(TypedDict):
    """Options for fetching a single branch."""

    repo_name: str
    branch_name: str

class ListBranchOptions(TypedDict):
    """Options for listing branches."""

    repo_name: str

