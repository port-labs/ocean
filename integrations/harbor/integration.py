from typing import Literal
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from pydantic import Field


class ProjectSelector(Selector):
    """Selector for Harbor projects with filtering options."""

    query: str = Field(default="true", description="JQ query to filter projects")
    public: bool | None = Field(
        default=None,
        description="Filter projects by visibility (true=public, false=private, null=all)",
        alias="public",
    )
    name: str | None = Field(
        default=None,
        description="Filter projects by name (exact match or fuzzy with ~ prefix)",
        alias="name",
    )


class UserSelector(Selector):
    """Selector for Harbor users."""

    query: str = Field(default="true", description="JQ query to filter users")
    username: str | None = Field(
        default=None, description="Filter users by username", alias="username"
    )


class RepositorySelector(Selector):
    """Selector for Harbor repositories with filtering options."""

    query: str = Field(default="true", description="JQ query to filter repositories")
    project_name: str | None = Field(
        default=None,
        description="Filter repositories by project name",
        alias="projectName",
    )
    name_contains: str | None = Field(
        default=None,
        description="Filter repositories where name contains this string",
        alias="nameContains",
    )
    name_starts_with: str | None = Field(
        default=None,
        description="Filter repositories where name starts with this string",
        alias="nameStartsWith",
    )


class ArtifactSelector(Selector):
    """Selector for Harbor artifacts with filtering options."""

    query: str = Field(default="true", description="JQ query to filter artifacts")
    tag: str | None = Field(
        default=None, description="Filter artifacts by tag name", alias="tag"
    )
    digest: str | None = Field(
        default=None, description="Filter artifacts by digest", alias="digest"
    )
    labels: list[str] | None = Field(
        default=None, description="Filter artifacts by labels", alias="labels"
    )
    media_type: str | None = Field(
        default=None, description="Filter artifacts by media type", alias="mediaType"
    )
    with_scan_overview: bool = Field(
        default=True,
        description="Include vulnerability scan overview in artifact data",
        alias="withScanOverview",
    )
    with_tag: bool = Field(
        default=True,
        description="Include tag information in artifact data",
        alias="withTag",
    )
    with_label: bool = Field(
        default=False,
        description="Include label information in artifact data",
        alias="withLabel",
    )


class ProjectResourceConfig(ResourceConfig):
    """Resource configuration for Harbor projects."""

    kind: Literal["project"]
    selector: ProjectSelector


class UserResourceConfig(ResourceConfig):
    """Resource configuration for Harbor users."""

    kind: Literal["user"]
    selector: UserSelector


class RepositoryResourceConfig(ResourceConfig):
    """Resource configuration for Harbor repositories."""

    kind: Literal["repository"]
    selector: RepositorySelector


class ArtifactResourceConfig(ResourceConfig):
    """Resource configuration for Harbor artifacts."""

    kind: Literal["artifact"]
    selector: ArtifactSelector


class GoHarborPortAppConfig(PortAppConfig):
    """Port application configuration for GoHarbor integration."""

    resources: list[
        ProjectResourceConfig
        | UserResourceConfig
        | RepositoryResourceConfig
        | ArtifactResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)


class GoHarborIntegration(BaseIntegration):
    """GoHarbor integration class."""

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = GoHarborPortAppConfig
