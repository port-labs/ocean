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

    q: Optional[str] = Field(
        None, description="Harbor query string for filtering projects"
    )
    sort: Optional[str] = Field(None, description="Sort field (e.g., 'name', '-name')")


class HarborProjectsConfig(ResourceConfig):
    """Configuration for Harbor projects resource."""

    selector: HarborProjectsSelector
    kind: Literal["projects"]


class HarborUsersSelector(Selector):
    """Selector for Harbor users with filtering options."""

    q: Optional[str] = Field(
        None, description="Harbor query string for filtering users"
    )
    sort: Optional[str] = Field(
        None, description="Sort field (e.g., 'username', '-username')"
    )


class HarborUsersConfig(ResourceConfig):
    """Configuration for Harbor users resource."""

    selector: HarborUsersSelector
    kind: Literal["users"]


class HarborRepositoriesSelector(Selector):
    """Selector for Harbor repositories with filtering options."""

    q: Optional[str] = Field(
        None, description="Harbor query string for filtering repositories"
    )
    sort: Optional[str] = Field(None, description="Sort field (e.g., 'name', '-name')")


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
    q: Optional[str] = Field(
        None, description="Harbor query string for filtering artifacts"
    )
    sort: Optional[str] = Field(
        None, description="Sort field (e.g., 'creation_time', '-creation_time')"
    )
    with_tag: Optional[bool] = Field(None, description="Include tags in response")
    with_label: Optional[bool] = Field(None, description="Include labels in response")
    with_scan_overview: Optional[bool] = Field(
        None, description="Include scan overview"
    )
    with_sbom_overview: Optional[bool] = Field(
        None, description="Include SBOM overview"
    )
    with_signature: Optional[bool] = Field(
        None, description="Include signature (requires with_tag=true)"
    )
    with_immutable_status: Optional[bool] = Field(
        None, description="Include immutable status (requires with_tag=true)"
    )
    with_accessory: Optional[bool] = Field(None, description="Include accessories")


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
