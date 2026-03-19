from typing import Any, ClassVar, Literal

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import BaseModel, Field
from enum import StrEnum


class ObjectKind(StrEnum):
    INCIDENT = "incident"
    USER_GROUP = "sys_user_group"
    SERVICE_CATALOG = "sc_catalog"
    VULNERABILITY = "sn_vul_vulnerable_item"
    RELEASE_PROJECT = "release_project"


class APIQueryParams(BaseModel):
    sysparm_display_value: Literal["true", "false", "all"] | None = Field(
        alias="sysparmDisplayValue",
        default="true",
        title="Display Value",
        description="Determines the type of data returned, either the actual values from the database or the display values of the fields",
    )
    sysparm_fields: str | None = Field(
        alias="sysparmFields",
        default=None,
        title="Fields",
        description="Comma-separated list of fields to return in the response",
    )
    sysparm_exclude_reference_link: Literal["true", "false"] | None = Field(
        alias="sysparmExcludeReferenceLink",
        default="false",
        title="Exclude Reference Link",
        description="Flag that indicates whether to exclude Table API links for reference fields",
    )
    sysparm_query: str | None = Field(
        alias="sysparmQuery",
        title="Query",
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
        title="API Query Params",
        description="The query parameters used to filter resources from the ServiceNow API",
    )


class IncidentResourceConfig(ResourceConfig):
    selector: ResourceSelector
    kind: Literal[ObjectKind.INCIDENT] = Field(
        title="ServiceNow Incident",
        description="A ServiceNow incident record from the incident table",
    )


class UserGroupResourceConfig(ResourceConfig):
    selector: ResourceSelector
    kind: Literal[ObjectKind.USER_GROUP] = Field(
        title="ServiceNow User Group",
        description="A ServiceNow user group from the sys_user_group table",
    )


class ServiceCatalogResourceConfig(ResourceConfig):
    selector: ResourceSelector
    kind: Literal[ObjectKind.SERVICE_CATALOG] = Field(
        title="ServiceNow Service Catalog",
        description="A ServiceNow service catalog from the sc_catalog table",
    )


class VulnerabilityResourceConfig(ResourceConfig):
    selector: ResourceSelector
    kind: Literal[ObjectKind.VULNERABILITY] = Field(
        title="ServiceNow Vulnerability",
        description="A ServiceNow vulnerable item from the sn_vul_vulnerable_item table",
    )


class ReleaseProjectResourceConfig(ResourceConfig):
    selector: ResourceSelector
    kind: Literal[ObjectKind.RELEASE_PROJECT] = Field(
        title="ServiceNow Release Project",
        description="A ServiceNow release project from the release_project table",
    )


class CustomResource(ResourceConfig):
    selector: ResourceSelector
    kind: str = Field(
        title="Custom kind",
        description="Use this to map additional ServiceNow resources by setting the kind name to any table available through the ServiceNow <a target='_blank' href='https://developer.servicenow.com/dev.do#!/reference/api/xanadu/rest/c_TableAPI#table-GET'>Table API</a>.\n\nExample: incident",
    )


class ServiceNowPortAppConfig(PortAppConfig):
    resources: list[
        IncidentResourceConfig
        | UserGroupResourceConfig
        | ServiceCatalogResourceConfig
        | VulnerabilityResourceConfig
        | ReleaseProjectResourceConfig
        | ResourceConfig
    ] = Field(default_factory=list)
    allow_custom_kinds: ClassVar[bool] = True


class ServiceNowIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ServiceNowPortAppConfig
