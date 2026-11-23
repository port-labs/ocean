from typing import Literal, Optional

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.v1 import Field, validator

from incident_io.core.options import AlertStatus, IncidentStatusCategory
from incident_io.helpers.utils import ObjectKind

# Five calendar years of 365 days. A longer window pulls too much history for large accounts.
MAX_DAYS_BACK = 5 * 365


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


class AlertSelector(Selector):
    days_back: int = Field(
        default=90,
        alias="daysBack",
        ge=1,
        le=MAX_DAYS_BACK,
        title="Days back",
        description=(
            "Sync alerts created in the last N days. Default is 90. "
            f"The maximum is {MAX_DAYS_BACK} days, about 5 years. "
            "Incremental runs stay inside this window and only refresh alerts "
            "updated since the cursor."
        ),
    )
    statuses: Optional[list[AlertStatus]] = Field(
        default=None,
        title="Statuses",
        description=(
            "Only sync alerts in these statuses. Leave empty to sync firing and resolved alerts."
        ),
    )


class AlertResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.ALERT] = Field(
        title="incident.io Alert",
        description="Fired and resolved alerts from alert sources.",
    )
    selector: AlertSelector = Field(
        title="Alert Selector",
        description="Time window and which alert statuses to sync.",
    )


class IncidentSelector(Selector):
    days_back: int = Field(
        default=90,
        alias="daysBack",
        ge=1,
        le=MAX_DAYS_BACK,
        title="Days back",
        description=(
            "Sync incidents created in the last N days. Default is 90 (about 3 months). "
            f"The maximum is {MAX_DAYS_BACK} days, about 5 years. "
            "Incremental runs stay inside this window and only refresh incidents updated since the cursor."
        ),
    )
    status_categories: Optional[list[IncidentStatusCategory]] = Field(
        default=None,
        alias="statusCategories",
        title="Status categories",
        description=(
            "Only sync incidents in these status categories. Leave empty to sync every category. "
            "The dashboard name Active is live, and Post-incident is learning."
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
        | AlertResourceConfig
        | IncidentResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]


class IncidentIoIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = IncidentIoPortAppConfig
