from typing import Literal, Any, Union

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
    PROJECTS = "projects"
    ISSUES = "issues"
    ANALYSIS = "analysis"
    SASS_ANALYSIS = "saas_analysis"
    ONPREM_ANALYSIS = "onprem_analysis"


class SonarQubeComponentSearchFilter(BaseModel):
    query: str | None
    metrics: list[dict[str, str]] | None
    alert_status: str | None
    languages: Union[str, list[str]] | None
    tags: Union[str, list[str]] | None
    qualifier: Literal["TRK", "APP"] | None

    def generate_search_filters(self) -> str:
        params = []
        for field, value in self.dict(exclude_none=True).items():
            if value is not None:
                if field == "metrics":
                    for metric_filter in value:
                        for metric_key, metric_value in metric_filter.items():
                            params.append(f"{metric_key} {metric_value}")
                elif field in ["languages", "tags"]:
                    if isinstance(value, list):
                        params.append(f"{field} IN ({','.join(value)})")
                    else:
                        params.append(f"{field}={value}")
                else:
                    params.append(f"{field}={value}")
        return " and ".join(params)


class SonarQubeProjectAPIQueryParams(BaseModel):
    q: str | None
    s: str | None
    filter: SonarQubeComponentSearchFilter | None

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if filter := value.pop("filter", None):
            filter_instance = SonarQubeComponentSearchFilter(**filter)
            value["filter"] = filter_instance.generate_search_filters()
        if q := value.pop("q", None):
            value["q"] = q
        if s := value.pop("s", None):
            value["s"] = s

        return value


class SonarQubeIssueAPIQueryParams(BaseModel):
    assigned: Literal["yes", "no", "true", "false"] | None
    assignees: list[str] | None
    clean_code_attribute_categories: (
        list[
            Literal[
                "ADAPTABLE",
                "CONSISTENT",
                "INTENTIONAL",
                "RESPONSIBLE",
            ]
        ]
        | None
    ) = Field(alias="cleanCodeAttributeCategories")
    code_variants: list[str] | None = Field(alias="codeVariants")
    created_before: str | None = Field(alias="createdBefore")
    created_after: str | None = Field(alias="createdAfter")
    cwe: list[str] | None
    impact_severities: list[Literal["HIGH", "LOW", "MEDIUM"]] | None = Field(
        alias="impactSeverities"
    )
    impact_software_qualities: (
        list[Literal["MAINTAINABILITY", "RELIABILITY", "SECURITY"]] | None
    ) = Field(alias="impactSoftwareQualities")
    statuses: (
        list[Literal["OPEN", "CONFIRMED", "FALSE_POSITIVE", "ACCEPTED", "FIXED"]] | None
    )
    languages: list[str] | None
    owasp_asvs_level: Literal["1", "2", "3"] | None = Field(alias="owaspAsvsLevel")
    resolved: Literal["yes", "no", "true", "false"] | None
    rules: list[str] | None
    scopes: list[Literal["MAIN", "TESTS"]] | None
    sonarsource_security: list[str] | None = Field(alias="sonarsourceSecurity")
    tags: list[str] | None

    def transform_underscore_to_camelcase(self, value: str) -> str:
        components = value.split("_")
        return components[0] + "".join(x.capitalize() for x in components[1:])

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)

        for key in list(value.keys()):
            val = value[key]
            if val is None:
                continue

            ## SonarQube API expects camelcase keys for query parameters
            camelcase_key = self.transform_underscore_to_camelcase(key)
            value[camelcase_key] = ",".join(val) if isinstance(val, list) else val

        return value


class SonarQubeProjectResourceConfig(ResourceConfig):
    class SonarQubeProjectSelector(Selector):
        api_query_params: SonarQubeProjectAPIQueryParams | None = Field(
            alias="apiQueryParams"
        )

    kind: Literal["projects"]
    selector: SonarQubeProjectSelector


class SonarQubeIssueResourceConfig(ResourceConfig):
    class SonarQubeIssueSelector(Selector):
        api_query_params: SonarQubeIssueAPIQueryParams | None = Field(
            alias="apiQueryParams"
        )

    kind: Literal["issues"]
    selector: SonarQubeIssueSelector


class SonarQubePortAppConfig(PortAppConfig):
    resources: list[
        Union[
            SonarQubeProjectResourceConfig, SonarQubeIssueResourceConfig, ResourceConfig
        ]
    ] = Field(default_factory=list)


class SonarQubeIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = SonarQubePortAppConfig
