"""Harbor integration options for filtering and configuration."""

from typing import NotRequired, Optional, TypedDict


class ListProjectOptions(TypedDict):
    """Options for listing Harbor projects with filtering."""

    q: NotRequired[Optional[str]]
    sort: NotRequired[Optional[str]]


class ListUserOptions(TypedDict):
    """Options for listing Harbor users with filtering."""

    q: NotRequired[Optional[str]]
    sort: NotRequired[Optional[str]]


class ListRepositoryOptions(TypedDict):
    """Options for listing Harbor repositories with filtering."""

    project_name: str
    q: NotRequired[Optional[str]]
    sort: NotRequired[Optional[str]]


class ListArtifactOptions(TypedDict):
    """Options for listing Harbor artifacts with filtering and enrichment."""

    project_name: str
    repository_name: str
    q: NotRequired[Optional[str]]
    sort: NotRequired[Optional[str]]
    with_tag: NotRequired[Optional[bool]]
    with_label: NotRequired[Optional[bool]]
    with_scan_overview: NotRequired[Optional[bool]]
    with_sbom_overview: NotRequired[Optional[bool]]
    with_signature: NotRequired[Optional[bool]]
    with_immutable_status: NotRequired[Optional[bool]]
    with_accessory: NotRequired[Optional[bool]]
