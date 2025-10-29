
from port_ocean.core.handlers.port_app_config.models import (
    Selector
)

from pydantic import Field

"""Harbor Integration Configuration for Ocean.

This module defines the configuration structure for the Harbor integration,
including selectors, resource configs, and the main integration class.
"""

# ============================================================================
# Selectors - Define user-configurable parameters for each kind
# ============================================================================


class ProjectSelector(Selector):
    """Selector for Harbor Projects.

    Allows users to filter and configure which projects to ingest.
    """

    query: str = Field(
        default="",
        description="Query string to filter projects (e.g., 'name=~library'). "
                    "Supports name, public, and owner filters."
    )

    include_metadata: bool = Field(
        default=True,
        description="Include project metadata such as CVE allowlist and storage quota"
    )

    page_size: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Number of projects to fetch per API call (1-500)"
    )


class UserSelector(Selector):
    """Selector for Harbor Users.

    Allows users to filter and configure which users to ingest.
    """

    username: str = Field(
        default="",
        description="Filter users by username (supports partial matching)"
    )

    include_system_users: bool = Field(
        default=False,
        description="Include system users in the ingestion"
    )

    page_size: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Number of users to fetch per API call (1-500)"
    )


class RepositorySelector(Selector):
    """Selector for Harbor Repositories.

    Allows users to filter and configure which repositories to ingest.
    """

    project_name: str = Field(
        default="",
        description="Filter repositories by project name. "
                    "If not specified, repositories from all projects will be fetched."
    )

    query: str = Field(
        default="",
        description="Query string to filter repositories (e.g., 'name=~nginx')"
    )

    include_pull_count: bool = Field(
        default=True,
        description="Include pull count statistics for repositories"
    )

    page_size: int = Field(
        default=100,
        ge=1,
        le=500,
        description="Number of repositories to fetch per API call (1-500)"
    )


class ArtifactSelector(Selector):
    """Selector for Harbor Artifacts.

    Allows users to filter and configure which artifacts to ingest.
    """

    project_name: str = Field(
        default="",
        description="Filter artifacts by project name. "
                    "If not specified, artifacts from all projects will be fetched."
    )

    repository_name: str = Field(
        default="",
        description="Filter artifacts by repository name within the specified project"
    )

    query: str = Field(
        default="",
        description="Query string to filter artifacts (e.g., 'tags=~v1.*')"
    )

    include_vulnerabilities: bool = Field(
        default=True,
        description="Include vulnerability scan results for artifacts"
    )

    include_build_history: bool = Field(
        default=False,
        description="Include build history information for artifacts"
    )

    with_tag: bool = Field(
        default=True,
        alias="withTag",
        description="Include only artifacts with tags (excludes untagged artifacts)"
    )

    with_scan_overview: bool = Field(
        default=True,
        alias="withScanOverview",
        description="Include scan overview information in the artifact data"
    )

    page_size: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Number of artifacts to fetch per API call (1-500). "
                    "Lower values recommended due to potentially large response sizes."
    )
