from typing import Any, Literal
from pydantic import Field, BaseModel

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class APIQueryParams(BaseModel):
    created_at: str | None = Field(
        alias="createdAt",
        description="The date and time the alert or incident was created",
    )
    last_occurred_at: str | None = Field(
        alias="lastOccurredAt",
        description="The date and time the alert was last occurred",
    )
    snoozed_until: str | None = Field(
        alias="snoozedUntil",
        description="The date and time the alert was snoozed until",
    )
    message: str | None = Field(description="The message of the alert or incident")
    status: Literal["open", "resolved", "closed"] | None = Field(
        description="The status of the alert"
    )
    is_seen: bool | None = Field(description="Whether the alert has been seen")
    acknowledged: bool | None = Field(
        description="Whether the alert has been acknowledged"
    )
    snoozed: bool | None = Field(description="Whether the alert has been snoozed")
    priority: Literal["P1", "P2", "P3", "P4", "P5"] | None = Field(
        description="The priority of the alert"
    )
    owner: str | None = Field(
        description="The owner of the alert. Accepts OpsGenie username"
    )
    teams: str | None = Field(description="The teams associated with the alert")
    acknowledged_by: str | None = Field(
        alias="acknowledgedBy", description="The user who acknowledged the alert"
    )
    closed_by: str | None = Field(
        alias="closedBy", description="The user who closed the alert"
    )

    def generate_request_params(self) -> dict[str, Any]:
        params = []
        for field, value in self.dict(exclude_none=True).items():
            if isinstance(value, list):
                params.append(f"{field}:{','.join(value)}")
            else:
                params.append(f"{field}:{value}")

        return {"query": " AND ".join(params)}

    class Config:
        allow_population_by_field_name = True  # This allows fields in a model to be populated either by their alias or by their field name


class ScheduleAPIQueryParams(BaseModel):
    expand: Literal["rotation"] | None = Field(
        description="The field to expand in the response"
    )

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if expand := value.pop("expand", None):
            value["expand"] = expand

        return value


class AlertAndIncidentSelector(Selector):
    api_query_params: APIQueryParams | None = Field(
        alias="apiQueryParams",
        description="The query parameters to filter alerts or incidents",
    )


class ScheduleSelector(Selector):
    api_query_params: ScheduleAPIQueryParams | None = Field(
        alias="apiQueryParams",
        description="The query parameters to filter schedules",
    )


class AlertAndIncidentResourceConfig(ResourceConfig):
    kind: Literal["alert", "incident"]
    selector: AlertAndIncidentSelector


class ScheduleResourceConfig(ResourceConfig):
    kind: Literal["schedule"]
    selector: ScheduleSelector


class OpsGeniePortAppConfig(PortAppConfig):
    resources: list[
        AlertAndIncidentResourceConfig | ScheduleResourceConfig | ResourceConfig
    ] = Field(default_factory=list)


class OpsGenieIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = OpsGeniePortAppConfig
