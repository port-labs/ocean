from typing import Literal, Any

from pydantic.fields import Field
from pydantic.main import BaseModel

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration

from clients.utils import (
    get_date_range_for_last_n_months,
    get_date_range_for_upcoming_n_months,
)


class ObjectKind:
    SERVICES = "services"
    INCIDENTS = "incidents"
    SCHEDULES = "schedules"
    ONCALLS = "oncalls"
    ESCALATION_POLICIES = "escalation_policies"


class PagerdutyServiceAPIQueryParams(BaseModel):
    include: (
        list[
            Literal[
                "escalation_policies",
                "teams",
                "integrations",
                "auto_pause_notifications_parameters",
            ]
        ]
        | None
    )
    sort_by: Literal["name", "name:asc", "name:desc"] | None
    team_ids: list[str] | None
    time_zone: str | None

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if include := value.pop("include", None):
            value["include[]"] = include
        if team_ids := value.pop("team_ids", None):
            value["team_ids[]"] = team_ids

        return value


class PagerdutyScheduleAPIQueryParams(BaseModel):
    include: list[str] | None

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if include := value.pop("include", None):
            value["include[]"] = include
        return value


class PagerdutyOncallAPIQueryParams(BaseModel):
    include: list[str] = Field(default=["users"])
    until: int = Field(default=3)
    since: int = Field(default=0)

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if include := value.pop("include", None):
            value["include[]"] = include
        if until := value.pop("until", None):
            value["until"] = get_date_range_for_upcoming_n_months(until)[1]
        if since := value.pop("since", None):
            value["since"] = get_date_range_for_last_n_months(since)[0]

        return value


class PagerdutyEscalationPolicyAPIQueryParams(BaseModel):
    include: list[Literal["services", "teams", "targets"]] | None
    team_ids: list[str] | None
    user_ids: list[str] | None

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if include := value.pop("include", None):
            value["include[]"] = include
        if team_ids := value.pop("team_ids", None):
            value["team_ids[]"] = team_ids
        if user_ids := value.pop("user_ids", None):
            value["user_ids[]"] = user_ids

        return value


class PagerdutyIncidentAPIQueryParams(BaseModel):
    date_range: str | None
    incident_key: str | None
    include: list[str] | None
    service_ids: list[str] | None
    since: str | None
    sort_by: str | None
    statuses: list[Literal["triggered", "acknowledged", "resolved"]] | None
    team_ids: list[str] | None
    time_zone: str | None
    until: str | None
    urgencies: list[Literal["high", "low"]] | None
    user_ids: list[str] | None

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if include := value.pop("include", None):
            value["include[]"] = include
        if service_ids := value.pop("service_ids", None):
            value["service_ids[]"] = service_ids
        if statuses := value.pop("statuses", None):
            value["statuses[]"] = statuses
        if team_ids := value.pop("team_ids", None):
            value["team_ids[]"] = team_ids
        if urgencies := value.pop("urgencies", None):
            value["urgencies[]"] = urgencies
        if user_ids := value.pop("user_ids", None):
            value["user_ids[]"] = user_ids

        return value


class PagerdutyIncidentResourceConfig(ResourceConfig):
    class PagerdutySelector(Selector):
        api_query_params: PagerdutyIncidentAPIQueryParams | None = Field(
            alias="apiQueryParams"
        )
        incident_analytics: bool = Field(
            default=False,
            description="If set to true, will ingest incident analytics data to Port. Default value is false",
            alias="incidentAnalytics",
        )

    kind: Literal["incidents"]
    selector: PagerdutySelector


class PagerdutyServiceResourceConfig(ResourceConfig):
    class PagerdutySelector(Selector):
        api_query_params: PagerdutyServiceAPIQueryParams | None = Field(
            alias="apiQueryParams"
        )
        service_analytics: bool = Field(
            default=True,
            description="If set to true, will ingest service analytics data to Port. Default value is true",
            alias="serviceAnalytics",
        )
        analytics_months_period: int = Field(
            default=3,
            description="Number of months to consider for the service analytics date range. Must be a positive integer. Default value is 3 months",
            alias="analyticsMonthsPeriod",
        )

    kind: Literal["services"]
    selector: PagerdutySelector


class PagerdutyScheduleResourceConfig(ResourceConfig):
    class PagerdutySelector(Selector):
        api_query_params: PagerdutyScheduleAPIQueryParams | None = Field(
            alias="apiQueryParams"
        )

    kind: Literal["schedules"]
    selector: PagerdutySelector


class PagerdutyOncallResourceConfig(ResourceConfig):
    class PagerdutySelector(Selector):
        api_query_params: PagerdutyOncallAPIQueryParams | None = Field(
            alias="apiQueryParams"
        )

    kind: Literal["oncalls"]
    selector: PagerdutySelector


class PagerdutyEscalationPolicyResourceConfig(ResourceConfig):
    class PagerdutySelector(Selector):
        api_query_params: PagerdutyEscalationPolicyAPIQueryParams | None = Field(
            alias="apiQueryParams"
        )
        attach_oncall_users: bool = Field(
            alias="attachOncallUsers",
            description=" When set to true, it fetches the oncall data per escalation policy",
            default=True,
        )

    kind: Literal["escalation_policies"]
    selector: PagerdutySelector


class PagerdutyPortAppConfig(PortAppConfig):
    resources: list[
        PagerdutyIncidentResourceConfig
        | PagerdutyServiceResourceConfig
        | PagerdutyScheduleResourceConfig
        | PagerdutyOncallResourceConfig
        | PagerdutyEscalationPolicyResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore


class PagerdutyIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = PagerdutyPortAppConfig
