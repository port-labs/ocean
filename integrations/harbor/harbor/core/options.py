"""Harbor integration options for filtering and configuration."""

from typing import NotRequired, Optional, Required, TypedDict, Union
from datetime import datetime


class SingleProjectOptions(TypedDict):
    """Options for fetching a single Harbor project."""

    project_name: Required[str]


class ListProjectOptions(TypedDict):
    """Options for listing Harbor projects with filtering."""

    name_prefix: NotRequired[Optional[str]]
    visibility: NotRequired[Optional[str]]  # "public" or "private"
    owner: NotRequired[Optional[str]]
    public: NotRequired[Optional[bool]]


class SingleUserOptions(TypedDict):
    """Options for fetching a single Harbor user."""

    user_id: Required[int]


class ListUserOptions(TypedDict):
    """Options for listing Harbor users with filtering."""

    username_prefix: NotRequired[Optional[str]]
    email: NotRequired[Optional[str]]
    admin_only: NotRequired[Optional[bool]]


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single Harbor repository."""

    project_name: Required[str]
    repository_name: Required[str]


class ListRepositoryOptions(TypedDict):
    """Options for listing Harbor repositories with filtering."""

    project_name: NotRequired[Optional[str]]
    repository_name: NotRequired[Optional[str]]
    label: NotRequired[Optional[str]]
    q: NotRequired[Optional[str]]  # Harbor query string


class SingleArtifactOptions(TypedDict):
    """Options for fetching a single Harbor artifact."""

    project_name: Required[str]
    repository_name: Required[str]
    reference: Required[str]  # tag or digest


class ListArtifactOptions(TypedDict):
    """Options for listing Harbor artifacts with filtering."""

    project_name: Required[str]
    repository_name: Required[str]
    tag: NotRequired[Optional[str]]
    digest: NotRequired[Optional[str]]
    label: NotRequired[Optional[str]]
    media_type: NotRequired[Optional[str]]
    created_since: NotRequired[Optional[Union[str, datetime]]]
    severity_threshold: NotRequired[
        Optional[str]
    ]  # "Low", "Medium", "High", "Critical"
    with_scan_overview: NotRequired[Optional[bool]]
    q: NotRequired[Optional[str]]  # Harbor query string
