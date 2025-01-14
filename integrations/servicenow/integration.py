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
    sysparm_display_value: Literal["true", "false", "all"] | None = Field(
        alias="sysparmDisplayValue",
        default="true",
        description="Determines the type of data returned, either the actual values from the database or the display values of the fields",
    )
    sysparm_fields: str | None = Field(
        alias="sysparmFields",
        description="Comma-separated list of fields to return in the response",
        default=None,
    )
    sysparm_exclude_reference_link: Literal["true", "false"] | None = Field(
        alias="sysparmExcludeReferenceLink",
        default="false",
        description="Flag that indicates whether to exclude Table API links for reference fields",
    )
    sysparm_query: str | None = Field(
        alias="sysparmQuery",
        description=(
            "Encoded query used to filter the result set. Syntax: <col_name><operator><value>"
            "<col_name>: Name of the table column to filter against"
            "<operator>: =, !=, ^, ^OR, LIKE, STARTSWITH, ENDSWITH, ORDERBY<col_name>, ORDERBYDESC<col_name>"
            "<value>: Value to match against"
            "Queries can be chained using ^ or ^OR for AND/OR logic. Example: active=true^nameLIKEincident^urgency=3"
        ),
    )

    def generate_request_params(self) -> dict[str, Any]:
        params = {}
        for field, value in self.dict(exclude_none=True).items():
            params[field] = value
        return params

    class Config:
        allow_population_by_field_name = True  # This allows fields in a model to be populated either by their alias or by their field name


class ResourceSelector(Selector):
    api_query_params: APIQueryParams | None = Field(
        alias="apiQueryParams",
        default_factory=APIQueryParams,
        description="The query parameters used to filter resources from the ServiceNow API",
    )


class ServiceNowResourceConfig(ResourceConfig):
    selector: ResourceSelector


class ServiceNowPortAppConfig(PortAppConfig):
    resources: list[ServiceNowResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )


class ServiceNowIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ServiceNowPortAppConfig
