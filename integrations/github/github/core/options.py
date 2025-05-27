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
