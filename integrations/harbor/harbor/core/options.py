"""Harbor integration options for filtering and configuration."""

from typing import NotRequired, Optional, Required, TypedDict


class SingleProjectOptions(TypedDict):
    """Options for fetching a single Harbor project."""

    project_name: Required[str]


class ListProjectOptions(TypedDict):
    """Options for listing Harbor projects with filtering."""

    q: NotRequired[Optional[str]]
    sort: NotRequired[Optional[str]]


class SingleUserOptions(TypedDict):
    """Options for fetching a single Harbor user."""

    user_id: Required[int]


class ListUserOptions(TypedDict):
    """Options for listing Harbor users with filtering."""

    q: NotRequired[Optional[str]]
    sort: NotRequired[Optional[str]]


class SingleRepositoryOptions(TypedDict):
    """Options for fetching a single Harbor repository."""

    project_name: Required[str]
    repository_name: Required[str]


class ListRepositoryOptions(TypedDict):
    """Options for listing Harbor repositories with filtering."""

    q: NotRequired[Optional[str]]
    sort: NotRequired[Optional[str]]


class SingleArtifactOptions(TypedDict):
    """Options for fetching a single Harbor artifact."""

    project_name: Required[str]
    repository_name: Required[str]
    reference: Required[str]


class ListArtifactOptions(TypedDict):
    """Options for listing Harbor artifacts with filtering."""

    project_name: Required[str]
    repository_name: Required[str]
    q: NotRequired[Optional[str]]
    sort: NotRequired[Optional[str]]
    with_tag: NotRequired[Optional[bool]]
    with_label: NotRequired[Optional[bool]]
    with_scan_overview: NotRequired[Optional[bool]]
    with_sbom_overview: NotRequired[Optional[bool]]
    with_signature: NotRequired[Optional[bool]]
    with_immutable_status: NotRequired[Optional[bool]]
    with_accessory: NotRequired[Optional[bool]]
