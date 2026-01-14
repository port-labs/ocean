"""TypedDict definitions for Harbor exporter options."""

from typing import Optional, TypedDict


class ListProjectOptions(TypedDict, total=False):
    """Options for listing projects."""

    public: Optional[bool]


class ListRepositoryOptions(TypedDict, total=False):
    """Options for listing repositories."""

    pass


class ListArtifactOptions(TypedDict, total=False):
    """Options for listing artifacts."""

    tag: Optional[str]
    digest: Optional[str]
    label: Optional[str]
    media_type: Optional[str]
    created_since: Optional[str]


class GetArtifactOptions(TypedDict):
    """Options for getting a single artifact."""

    project_name: str
    repository_name: str
    reference: str


class ListUserOptions(TypedDict, total=False):
    """Options for listing users."""

    pass

