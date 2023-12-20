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


class ObjectKind:
    SERVICES = "services"
    INCIDENTS = "incidents"
    SCHEDULES = "schedules"


class PagerdutyServiceAPIQueryParams(BaseModel):
    include: list[
        Literal[
            "escalation_policies",
            "teams",
            "integrations",
            "auto_pause_notifications_parameters",
        ]
    ] | None
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
    include: list[Literal["escalation_policies", "users"]] | None

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if include := value.pop("include", None):
            value["include[]"] = include
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

    kind: Literal["incidents"]
    selector: PagerdutySelector


class PagerdutyServiceResourceConfig(ResourceConfig):
    class PagerdutySelector(Selector):
        api_query_params: PagerdutyServiceAPIQueryParams | None = Field(
            alias="apiQueryParams"
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


class PagerdutyPortAppConfig(PortAppConfig):
    resources: list[
        PagerdutyIncidentResourceConfig
        | PagerdutyServiceResourceConfig
        | PagerdutyScheduleResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore


class PagerdutyIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = PagerdutyPortAppConfig
