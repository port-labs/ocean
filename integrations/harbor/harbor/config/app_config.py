# ResourceConfigs - Link selectors to specific resource kinds
# ============================================================================
from typing import Literal
from pydantic import Field
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import EntityMapping, MappingsConfig, PortAppConfig, PortResourceConfig, ResourceConfig
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
            selector=ProjectSelector(),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".project_id",
                        title=".name",
                        blueprint="harborProject",
                        properties={
                            "projectId": ".project_id",
                            "public": ".metadata.public",
                            "ownerId": ".owner_id",
                            "ownerName": ".owner_name",
                            "creationTime": ".creation_time",
                            "updateTime": ".update_time",
                            "repoCount": ".repo_count",
                            "chartCount": ".chart_count",
                            "storageLimit": ".storage_limit",
                            "registryId": ".registry_id",
                            "cveSeverity": ".cve_severity",
                            "memberCount": ".member_count",
                        },
                        relations={},
                    )
                )
            ),
        ),
        UserResourceConfig(
            kind="user",
            selector=UserSelector(query="true"),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".user_id",
                        title=".username",
                        blueprint="harborUser",
                        properties={
                            "userId": ".user_id",
                            "username": ".username",
                            "email": ".email",
                            "realname": ".realname",
                            "comment": ".comment",
                            "adminRoleInAuth": ".admin_role_in_auth",
                            "creationTime": ".creation_time",
                            "updateTime": ".update_time",
                            "sysadminFlag": ".sysadmin_flag",
                        },
                        relations={},
                    )
                )
            ),
        ),
        RepositoryResourceConfig(
            kind="repository",
            selector=RepositorySelector(),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".repository_id",
                        title=".name",
                        blueprint="harborRepository",
                        properties={
                            "repositoryId": ".repository_id",
                            "name": ".name",
                            "projectId": ".project_id",
                            "description": ".description",
                            "artifactCount": ".artifact_count",
                            "pullCount": ".pull_count",
                            "creationTime": ".creation_time",
                            "updateTime": ".update_time",
                        },
                        relations={
                            "project": ".project_id",
                        },
                    )
                )
            ),
        ),
        ArtifactResourceConfig(
            kind="artifact",
            selector=ArtifactSelector(),
            port=PortResourceConfig(
                entity=MappingsConfig(
                    mappings=EntityMapping(
                        identifier=".digest",
                        title=".digest",
                        blueprint="harborArtifact",
                        properties={
                            "digest": ".digest",
                            "size": ".size",
                            "pushTime": ".push_time",
                            "pullTime": ".pull_time",
                            "type": ".type",
                            "tags": ".tags",
                            "vulnerabilities": ".vulnerabilities",
                            "scanStatus": ".scan_status",
                            "severity": ".severity",
                            "criticalCount": ".critical_count",
                            "highCount": ".high_count",
                            "mediumCount": ".medium_count",
                            "lowCount": ".low_count",
                            "labels": ".labels",
                        },
                        relations={
                            "repository": ".repository_id",
                            "project": ".project_id",
                        },
                    )
                )
            ),
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