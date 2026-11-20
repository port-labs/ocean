from typing import Literal, Optional

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.v1 import Field, validator

from incident_io.helpers.utils import ObjectKind

# API values. The dashboard shows "live" as Active and "learning" as Post-incident.
STATUS_CATEGORIES = (
    "triage",
    "live",
    "learning",
    "paused",
    "closed",
    "declined",
    "canceled",
    "merged",
)


class UserSelector(Selector):
    include_inactive: bool = Field(
        default=False,
        alias="includeInactive",
        title="Include inactive users",
        description="Also sync deactivated and not-yet-active users. Default: active users only.",
    )


class UserResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.USER] = Field(
        title="incident.io User",
        description="People in the incident.io account.",
    )
    selector: UserSelector = Field(
        title="User Selector",
        description="Whether to include inactive users.",
    )


class TeamResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.TEAM] = Field(
        title="incident.io Team",
        description="Teams that own incidents and on-call schedules.",
    )


class ScheduleResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.SCHEDULE] = Field(
        title="incident.io Schedule",
        description="On-call schedules, including who is on call now.",
    )


class IncidentSelector(Selector):
    days_back: int = Field(
        default=180,
        alias="daysBack",
        ge=1,
        le=3650,
        title="Days back",
        description="Sync incidents created in the last N days. Default is 180 (about 6 months). Incremental runs stay inside this window and only refresh incidents updated since the cursor.",
    )
    status_categories: Optional[list[str]] = Field(
        default=None,
        alias="statusCategories",
        title="Status categories",
        description=(
            "Only sync incidents in these status categories. Default: all. "
            f"Allowed: {', '.join(STATUS_CATEGORIES)}. "
            "The dashboard name Active is 'live', and Post-incident is 'learning'."
        ),
    )
    severities: Optional[list[str]] = Field(
        default=None,
        title="Severities",
        description=(
            "Only sync incidents of these severities, by name or id. Default: all. "
            "Names are resolved to ids and sent as severity[one_of]."
        ),
    )
    include_test: bool = Field(
        default=False,
        alias="includeTest",
        title="Include test incidents",
        description="Also sync test and tutorial incidents. Default: standard and retrospective only.",
    )

    @validator("severities")
    def _check_severities(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if not value:
            return None
        cleaned = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("severities must be severity names or ids")
            cleaned.append(item.strip())
        return cleaned

    @validator("status_categories")
    def _check_status_categories(
        cls, value: Optional[list[str]]
    ) -> Optional[list[str]]:
        if not value:
            return None
        invalid = [item for item in value if item not in STATUS_CATEGORIES]
        if invalid:
            raise ValueError(f"Unknown incident status categories: {invalid}")
        return value


class IncidentResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.INCIDENT] = Field(
        title="incident.io Incident",
        description="Incidents, including status, severity, and who is involved.",
    )
    selector: IncidentSelector = Field(
        title="Incident Selector",
        description="Time window, status categories, severities, and whether test incidents are included.",
    )


class IncidentIoPortAppConfig(PortAppConfig):
    resources: list[
        UserResourceConfig
        | TeamResourceConfig
        | ScheduleResourceConfig
        | IncidentResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]


class IncidentIoIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = IncidentIoPortAppConfig
