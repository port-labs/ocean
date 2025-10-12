# ============================================================================
# ResourceConfigs - Link selectors to specific resource kinds
# ============================================================================



from typing import Literal

from pydantic import Field
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import PortAppConfig, ResourceConfig
from selectors import ProjectSelector, UserSelector, RepositorySelector, ArtifactSelector


class ProjectResourceConfig(ResourceConfig):
    """Resource configuration for Harbor Projects."""

    selector: ProjectSelector
    kind: Literal["project"]


class UserResourceConfig(ResourceConfig):
    """Resource configuration for Harbor Users."""

    selector: UserSelector
    kind: Literal["user"]


class RepositoryResourceConfig(ResourceConfig):
    """Resource configuration for Harbor Repositories."""

    selector: RepositorySelector
    kind: Literal["repository"]


class ArtifactResourceConfig(ResourceConfig):
    """Resource configuration for Harbor Artifacts."""

    selector: ArtifactSelector
    kind: Literal["artifact"]


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
                selector=ProjectSelector(),
                kind="project"
            ),
            UserResourceConfig(
                selector=UserSelector(),
                kind="user"
            ),
            RepositoryResourceConfig(
                selector=RepositorySelector(),
                kind="repository"
            ),
            ArtifactResourceConfig(
                selector=ArtifactSelector(),
                kind="artifact"
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

    if not all([harbor_url, username, password]):
        raise ValueError(
            "Missing required Harbor configuration. "
            "Ensure harbor_url, harbor_username, and harbor_password are configured."
        )

    return harbor_url, username, password, verify_ssl
