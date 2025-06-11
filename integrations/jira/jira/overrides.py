from typing import Literal

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field


class TeamSelector(Selector):
    include_members: bool = Field(
        alias="includeMembers",
        default=False,
        description="Whether to include the members of the team, defaults to false",
    )


class TeamResourceConfig(ResourceConfig):
    kind: Literal["team"]
    selector: TeamSelector


class JiraIssueSelector(Selector):
    jql: str | None = None
    fields: str | None = Field(
        description="Additional fields to be included in the API response",
        default="*all",
    )


class JiraIssueConfig(ResourceConfig):
    selector: JiraIssueSelector
    kind: Literal["issue"]


class JiraProjectSelector(Selector):
    expand: str = Field(
        description="A comma-separated list of the parameters to expand.",
        default="insight",
    )


class JiraProjectResourceConfig(ResourceConfig):
    selector: JiraProjectSelector
    kind: Literal["project"]


# Jira Service Management selectors and configurations
class JiraServiceManagementSelector(Selector):
    service_desk_id: str | None = Field(
        alias="serviceDeskId",
        description="Filter by Service Desk ID",
        default=None,
    )
    organization_id: str | None = Field(
        alias="organizationId",
        description="Filter by Organization ID",
        default=None,
    )


class JiraServiceResourceConfig(ResourceConfig):
    selector: JiraServiceManagementSelector
    kind: Literal["service"]


class JiraIncidentSelector(Selector):
    service_desk_id: str | None = Field(
        alias="serviceDeskId",
        description="Filter by Service Desk ID",
        default=None,
    )
    status: str | None = Field(
        description="Filter by incident status",
        default=None,
    )


class JiraIncidentResourceConfig(ResourceConfig):
    selector: JiraIncidentSelector
    kind: Literal["incident"]


class JiraRequestSelector(Selector):
    service_desk_id: str | None = Field(
        alias="serviceDeskId",
        description="Filter by Service Desk ID",
        default=None,
    )
    request_type_id: str | None = Field(
        alias="requestTypeId",
        description="Filter by request type ID",
        default=None,
    )


class JiraRequestResourceConfig(ResourceConfig):
    selector: JiraRequestSelector
    kind: Literal["request"]


class JiraAssetSelector(Selector):
    schema_id: str | None = Field(
        alias="schemaId",
        description="Filter by asset schema ID",
        default=None,
    )
    object_type_id: str | None = Field(
        alias="objectTypeId",
        description="Filter by object type ID",
        default=None,
    )


class JiraAssetResourceConfig(ResourceConfig):
    selector: JiraAssetSelector
    kind: Literal["asset"]


class JiraScheduleSelector(Selector):
    include_teams: bool = Field(
        alias="includeTeams",
        default=False,
        description="Whether to include team information in schedules",
    )


class JiraScheduleResourceConfig(ResourceConfig):
    selector: JiraScheduleSelector
    kind: Literal["schedule"]


class JiraPortAppConfig(PortAppConfig):
    resources: list[
        TeamResourceConfig
        | JiraIssueConfig
        | JiraProjectResourceConfig
        | JiraServiceResourceConfig
        | JiraIncidentResourceConfig
        | JiraRequestResourceConfig
        | JiraAssetResourceConfig
        | JiraScheduleResourceConfig
        | ResourceConfig
    ]
