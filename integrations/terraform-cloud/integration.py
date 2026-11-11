from typing import Literal, Optional

from pydantic.v1 import Field

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration

from utils import ObjectKind


class StateFileSelector(Selector):
    current_only: bool = Field(
        alias="currentOnly",
        default=True,
        title="Current Only",
        description="If true, fetch only the current state file per workspace. If false, fetch all historical state files.",
    )


class StateFileResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.STATE_FILE] = Field(
        title="Terraform State File",
        description="Terraform state file resource kind.",
    )
    selector: StateFileSelector = Field(
        title="Terraform State File Selector",
        description="Selector for the terraform state file resource.",
    )


class OrganizationResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.ORGANIZATION] = Field(
        title="Terraform Organization",
        description="Terraform organization resource kind.",
    )


class ProjectResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.PROJECT] = Field(
        title="Terraform Project",
        description="Terraform project resource kind.",
    )


class WorkspaceResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.WORKSPACE] = Field(
        title="Terraform Workspace",
        description="Terraform workspace resource kind.",
    )


class RunResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.RUN] = Field(
        title="Terraform Run",
        description="Terraform run resource kind.",
    )


class StateVersionResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.STATE_VERSION] = Field(
        title="Terraform State Version",
        description="Terraform state version resource kind.",
    )


class HealthAssessmentResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.HEALTH_ASSESSMENT] = Field(
        title="Terraform Health Assessment",
        description="Terraform health assessment resource kind.",
    )


class TeamSelector(Selector):
    search: Optional[str] = Field(
        default=None,
        title="Search",
        description="Fetch only teams whose name contains this string. Case-insensitive.",
    )

    def to_params(self) -> dict[str, str]:
        return {"q": self.search} if self.search else {}


class TeamResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.TEAM] = Field(
        title="Terraform Team",
        description="Terraform team resource kind.",
    )
    selector: TeamSelector = Field(
        title="Terraform Team Selector",
        description="Selector for the terraform team resource.",
    )


class OrganizationMembershipSelector(Selector):
    status: Optional[Literal["active", "invited"]] = Field(
        default=None,
        title="Status",
        description="Fetch only memberships with this status. Fetches both active members and pending invites when unset.",
    )

    search: Optional[str] = Field(
        default=None,
        title="Search",
        description="Fetch only memberships whose username or email contains this string. Case-insensitive.",
    )
    emails: Optional[list[str]] = Field(
        default=None,
        title="Emails",
        description="Fetch only the memberships with these exact email addresses. Case-sensitive.",
    )

    def to_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.status:
            params["filter[status]"] = self.status
        if self.search:
            params["q"] = self.search
        if self.emails:
            params["filter[email]"] = ",".join(self.emails)
        return params


class OrganizationMembershipResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.ORGANIZATION_MEMBERSHIP] = Field(
        title="Terraform Organization Membership",
        description="Terraform organization membership resource kind.",
    )
    selector: OrganizationMembershipSelector = Field(
        title="Terraform Organization Membership Selector",
        description="Selector for the terraform organization membership resource.",
    )


class TeamWorkspaceAccessResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.TEAM_WORKSPACE_ACCESS] = Field(
        title="Terraform Team Workspace Access",
        description="Terraform team workspace access resource kind.",
    )


class TeamProjectAccessResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.TEAM_PROJECT_ACCESS] = Field(
        title="Terraform Team Project Access",
        description="Terraform team project access resource kind.",
    )


class TerraformCloudPortAppConfig(PortAppConfig):
    resources: list[
        StateFileResourceConfig
        | OrganizationResourceConfig
        | ProjectResourceConfig
        | WorkspaceResourceConfig
        | RunResourceConfig
        | StateVersionResourceConfig
        | HealthAssessmentResourceConfig
        | TeamResourceConfig
        | OrganizationMembershipResourceConfig
        | TeamWorkspaceAccessResourceConfig
        | TeamProjectAccessResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]


class TerraformCloudIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = TerraformCloudPortAppConfig
