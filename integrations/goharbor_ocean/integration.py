"""Harbor integration configuration and handlers."""

from typing import Literal, Optional

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field


class HarborProjectSelector(Selector):
    """Selector for projects with filtering options."""

    q: Optional[str] = Field(None, description="Harbor query string for filtering projects")
    sort: Optional[str] = Field(None, description="Sort field (e.g. 'name', '-name')")


class HarborProjectConfig(ResourceConfig):
    """Configuration for projects resource."""

    selector: HarborProjectSelector
    kind: Literal["project"]


class HarborUserSelector(Selector):
    """Selector for users with filtering options."""

    q: Optional[str] = Field(None, description="Harbor query string for filtering users")
    sort: Optional[str] = Field(None, description="Sort field (e.g. 'username', '-username')")


class HarborUserConfig(ResourceConfig):
    """Configuration for users resource."""

    selector: HarborUserSelector
    kind: Literal["user"]


class HarborRepositorySelector(Selector):
    """Selector for repositories with filtering options."""

    q: Optional[str] = Field(None, description="Harbor query string for filtering repositories")
    sort: Optional[str] = Field(None, description="Sort field ('name', '-name')")


class HarborRepositoryConfig(ResourceConfig):
    """Configuration for repositories resource."""

    selector: HarborRepositorySelector
    kind: Literal["repository"]


class HarborArtifactSelector(Selector):
    """Selector for artifacts with filtering and enrichment options."""

    q: Optional[str] = Field(None, description="Harbor query string for filtering artifacts")
    sort: Optional[str] = Field(None, description="Sort field ('creation_time', '-creation_time')")
    with_tag: bool = Field(default=True, description="Include tags in response")
    with_label: bool = Field(default=True, description="Include labels in response")
    with_scan_overview: bool = Field(default=True, description="Include vulnerability scan overview")
    with_sbom_overview: bool = Field(default=False, description="Include SBOM overview")
    with_signature: bool = Field(default=False, description="Include signature (requires with_tag=true)")
    with_immutable_status: bool = Field(default=False, description="Include immutable status")
    with_accessory: bool = Field(default=False, description="Include accessories")


class HarborArtifactConfig(ResourceConfig):
    """Configuration for artifacts resource."""

    selector: HarborArtifactSelector
    kind: Literal["artifact"]


class HarborPortAppConfig(PortAppConfig):
    """Port app configuration for Harbor integration."""

    resources: list[
        HarborProjectConfig | HarborUserConfig | HarborRepositoryConfig | HarborArtifactConfig | ResourceConfig
    ] = Field(default_factory=list, description="List of Harbor resources to sync")


class HarborIntegration(BaseIntegration):
    """Harbor integration class."""

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = HarborPortAppConfig
