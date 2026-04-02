from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field
from typing import Literal
from port_ocean.core.integrations.base import BaseIntegration


class ProjectSelector(Selector):
    attach_issues_to_project: bool = Field(
        alias="attachIssuesToProject",
        default=True,
        title="Attach Issues to Project",
        description="Whether to attach issues to the project during ingestion.",
    )


class ProjectResourceConfig(ResourceConfig):
    kind: Literal["project"] = Field(
        title="Snyk Project",
        description="Snyk project resource kind.",
    )
    selector: ProjectSelector = Field(
        title="Project Selector",
        description="Selector for the Snyk project resource.",
    )


class TargetSelector(Selector):
    attach_project_data: bool = Field(
        default=True,
        alias="attachProjectData",
        title="Attach Project Data",
        description="Whether to attach project data to the target during ingestion.",
    )


class TargetResourceConfig(ResourceConfig):
    kind: Literal["target"] = Field(
        title="Snyk Target",
        description="Snyk target resource kind.",
    )
    selector: TargetSelector = Field(
        title="Target Selector",
        description="Selector for the Snyk target resource.",
    )


class OrganizationResourceConfig(ResourceConfig):
    kind: Literal["organization"] = Field(
        title="Snyk Organization",
        description="Snyk organization resource kind.",
    )


class VulnerabilityResourceConfig(ResourceConfig):
    kind: Literal["vulnerability"] = Field(
        title="Snyk Vulnerability",
        description="Snyk vulnerability resource kind.",
    )


class IssueResourceConfig(ResourceConfig):
    kind: Literal["issue"] = Field(
        title="Snyk Issue",
        description="Snyk issue resource kind.",
    )


class SnykPortAppConfig(PortAppConfig):
    resources: list[
        ProjectResourceConfig
        | TargetResourceConfig
        | OrganizationResourceConfig
        | VulnerabilityResourceConfig
        | IssueResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]


class SnykIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = SnykPortAppConfig
