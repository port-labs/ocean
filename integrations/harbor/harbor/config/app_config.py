# ResourceConfigs - Link selectors to specific resource kinds
# ============================================================================
from typing import Literal
from pydantic import Field
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import PortAppConfig, ResourceConfig
from .selectors import ProjectSelector, UserSelector, RepositorySelector, ArtifactSelector


class ProjectResourceConfig(ResourceConfig):
    """Resource configuration for Harbor Projects."""
    selector: ProjectSelector
    kind: Literal["project"] = "project"


class UserResourceConfig(ResourceConfig):
    """Resource configuration for Harbor Users."""
    selector: UserSelector
    kind: Literal["user"] = "user"


class RepositoryResourceConfig(ResourceConfig):
    """Resource configuration for Harbor Repositories."""
    selector: RepositorySelector
    kind: Literal["repository"] = "repository"


class ArtifactResourceConfig(ResourceConfig):
    """Resource configuration for Harbor Artifacts."""
    selector: ArtifactSelector
    kind: Literal["artifact"] = "artifact"


# ============================================================================
# PortAppConfig - Main integration configuration
# ============================================================================

class HarborPortAppConfig(PortAppConfig):
    """Main configuration for the Harbor integration.
    
    This class combines all resource configurations and defines the overall
    structure of the Harbor integration in Ocean.
    """
    resources: list[
        ProjectResourceConfig
        | UserResourceConfig
        | RepositoryResourceConfig
        | ArtifactResourceConfig
        | ResourceConfig
    ] = Field(
        default_factory=lambda: [
            ProjectResourceConfig(
                kind="project",
                selector=ProjectSelector()
            ),
            UserResourceConfig(
                kind="user",
                selector=UserSelector(query="true")
            ),
            RepositoryResourceConfig(
                kind="repository",
                selector=RepositorySelector()
            ),
            ArtifactResourceConfig(
                kind="artifact",
                selector=ArtifactSelector()
            ),
        ],
        description="List of resource configurations for Harbor entities to ingest"
    )


def get_harbor_config() -> tuple[str, str, str, bool]:
    """
    Extract Harbor configuration from ocean config.
    
    Returns:
        Tuple of (harbor_url, username, password, verify_ssl)
        
    Raises:
        ValueError: If required configuration is missing
    """
    harbor_url = ocean.integration_config.get("harbor_url")
    username = ocean.integration_config.get("harbor_username")
    password = ocean.integration_config.get("harbor_password")
    verify_ssl = ocean.integration_config.get("verify_ssl", True)
    
    if not harbor_url:
        raise ValueError("harbor_url is required in integration config")
    if not username:
        raise ValueError("harbor_username is required in integration config")
    if not password:
        raise ValueError("harbor_password is required in integration config")
    
    return harbor_url, username, password, verify_ssl