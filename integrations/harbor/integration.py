"""Harbor integration for Port Ocean."""

from typing import Literal, Optional

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration

from pydantic import Field


class ProjectSelector(Selector):
    """Selector configuration for Harbor projects."""
    
    public: Optional[bool] = Field(
        default=None,
        alias="public",
        description="Filter projects by public status"
    )


class ProjectResourceConfig(ResourceConfig):
    """Resource configuration for Harbor projects."""
    
    selector: ProjectSelector
    kind: Literal["/projects"]


class ArtifactSelector(Selector):
    """Selector configuration for Harbor artifacts."""
    
    tag: Optional[str] = Field(
        default=None,
        alias="tag",
        description="Filter artifacts by tag name"
    )
    digest: Optional[str] = Field(
        default=None,
        alias="digest",
        description="Filter artifacts by digest"
    )
    label: Optional[str] = Field(
        default=None,
        alias="label",
        description="Filter artifacts by label"
    )
    media_type: Optional[str] = Field(
        default=None,
        alias="media_type",
        description="Filter artifacts by media type"
    )
    created_since: Optional[str] = Field(
        default=None,
        alias="created_since",
        description="Filter artifacts created since (ISO 8601 date)"
    )


class ArtifactResourceConfig(ResourceConfig):
    """Resource configuration for Harbor artifacts."""
    
    selector: ArtifactSelector
    kind: Literal["/artifacts"]


class HarborPortAppConfig(PortAppConfig):
    """Port app configuration for Harbor integration."""
    
    resources: list[
        ProjectResourceConfig 
        | ArtifactResourceConfig 
        | ResourceConfig
    ]


class HarborIntegration(BaseIntegration):
    """Harbor integration class."""
    
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = HarborPortAppConfig
