"""Harbor integration configuration and handlers."""

from typing import Any, List, Literal, Union, Optional
from pydantic import Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.integrations.mixins.handler import HandlerMixin
from port_ocean.core.handlers.entity_processor.jq_entity_processor import (
    JQEntityProcessor,
)


class HarborProjectsSelector(Selector):
    """Selector for Harbor projects with filtering options."""

    name_prefix: Optional[str] = Field(
        None, description="Filter projects by name prefix"
    )
    visibility: Optional[str] = Field(
        None, description="Filter by visibility: 'public' or 'private'"
    )
    owner: Optional[str] = Field(None, description="Filter by project owner")


class HarborProjectsConfig(ResourceConfig):
    """Configuration for Harbor projects resource."""

    selector: HarborProjectsSelector
    kind: Literal["projects"]


class HarborUsersSelector(Selector):
    """Selector for Harbor users with filtering options."""

    username_prefix: Optional[str] = Field(
        None, description="Filter users by username prefix"
    )
    email: Optional[str] = Field(None, description="Filter by email address")
    admin_only: Optional[bool] = Field(None, description="Filter only admin users")


class HarborUsersConfig(ResourceConfig):
    """Configuration for Harbor users resource."""

    selector: HarborUsersSelector
    kind: Literal["users"]


class HarborRepositoriesSelector(Selector):
    """Selector for Harbor repositories with filtering options."""

    project_name: Optional[str] = Field(
        None, description="Filter repositories by project name"
    )
    repository_name: Optional[str] = Field(
        None, description="Filter by repository name"
    )
    label: Optional[str] = Field(None, description="Filter by repository label")
    q: Optional[str] = Field(
        None, description="Harbor query string for advanced filtering"
    )


class HarborRepositoriesConfig(ResourceConfig):
    """Configuration for Harbor repositories resource."""

    selector: HarborRepositoriesSelector
    kind: Literal["repositories"]


class HarborArtifactsSelector(Selector):
    """Selector for Harbor artifacts with filtering options."""

    project_name: Optional[str] = Field(
        None,
        description="Filter artifacts by project name (if not provided, will fetch from all projects)",
    )
    repository_name: Optional[str] = Field(
        None,
        description="Filter artifacts by repository name (if not provided, will fetch from all repositories)",
    )
    tag: Optional[str] = Field(None, description="Filter by artifact tag")
    digest: Optional[str] = Field(None, description="Filter by artifact digest")
    label: Optional[str] = Field(None, description="Filter by artifact label")
    media_type: Optional[str] = Field(None, description="Filter by media type")
    created_since: Optional[str] = Field(
        None, description="Filter artifacts created since date"
    )
    severity_threshold: Optional[str] = Field(
        None,
        description="Filter by vulnerability severity: 'Low', 'Medium', 'High', 'Critical'",
    )
    with_scan_overview: Optional[bool] = Field(
        None, description="Include vulnerability scan data"
    )
    q: Optional[str] = Field(
        None, description="Harbor query string for advanced filtering"
    )


class HarborArtifactsConfig(ResourceConfig):
    """Configuration for Harbor artifacts resource."""

    selector: HarborArtifactsSelector
    kind: Literal["artifacts"]


class HarborPortAppConfig(PortAppConfig):
    """Main Harbor integration configuration."""

    webhook_secret: Optional[str] = Field(
        None, description="Secret for Harbor webhook authentication"
    )

    resources: List[
        Union[
            HarborProjectsConfig,
            HarborUsersConfig,
            HarborRepositoriesConfig,
            HarborArtifactsConfig,
            ResourceConfig,  # Fallback for generic resources
        ]
    ] = Field(default_factory=list, description="List of Harbor resources to sync")


class HarborHandlerMixin(HandlerMixin):
    """Harbor-specific handler mixin."""

    EntityProcessorClass = JQEntityProcessor


class HarborIntegration(BaseIntegration, HarborHandlerMixin):
    """Main Harbor integration class."""

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = HarborPortAppConfig

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
