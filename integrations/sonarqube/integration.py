from abc import abstractmethod
from typing import Annotated, Any, Literal, Union

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.fields import Field
from pydantic.main import BaseModel


class ObjectKind:
    PROJECTS = "projects"
    PROJECTS_GA = "projects_ga"
    ISSUES = "issues"
    ANALYSIS = "analysis"
    SASS_ANALYSIS = "saas_analysis"
    ONPREM_ANALYSIS = "onprem_analysis"
    PORTFOLIOS = "portfolios"


class SonarQubeComponentSearchFilter(BaseModel):
    query: str | None = Field(
        description="Limit search to component names that contain the supplied string"
    )
    metrics: list[dict[str, str]] | None = Field(
        description="List of metric keys and their values such as security_rating>=2 or coverage<=80"
    )
    alert_status: str | None = Field(
        alias="alertStatus", description="To filter on a Quality Gate status"
    )
    languages: Union[str, list[str]] | None = Field(
        description="List of languages or a single language"
    )
    tags: Union[str, list[str]] | None = Field(
        description="List of tags or a single tag"
    )
    qualifier: Literal["TRK", "APP"] | None = Field(
        description="To filter on a component qualifier"
    )

    def generate_search_filters(self) -> str:
        params = []
        for field, value in self.dict(exclude_none=True).items():
            if field == "metrics":
                for metric_filter in value:
                    for metric_key, metric_value in metric_filter.items():
                        params.append(f"{metric_key} {metric_value}")
            elif field in ["languages", "tags"] and isinstance(value, list):
                params.append(f"{field} IN ({','.join(value)})")
            else:
                params.append(f"{field}={value}")
        return " and ".join(params)

    class Config:
        allow_population_by_field_name = True


class BaseSonarQubeApiFilter(BaseModel):
    @abstractmethod
    def generate_request_params(self) -> dict[str, Any]:
        pass


class SonarQubeProjectApiFilter(BaseSonarQubeApiFilter):
    filter: SonarQubeComponentSearchFilter | None

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if filter := value.pop("filter", None):
            filter_instance = SonarQubeComponentSearchFilter(**filter)
            value["filter"] = filter_instance.generate_search_filters()
        if s := value.pop("s", None):
            value["s"] = s

        return value


class SonarQubeGAProjectAPIFilter(BaseSonarQubeApiFilter):
    analyzed_before: str | None = Field(
        alias="analyzedBefore",
        description="To retrieve projects analyzed before the given date",
    )
    on_provisioned_only: bool | None = Field(
        alias="onProvisionedOnly",
        description="To retrieve projects on provisioned only",
    )
    projects: list[str] | None = Field(description="List of projects")
    qualifiers: list[Literal["TRK", "APP"]] | None = Field(
        description="List of qualifiers", alias="qualifier"
    )

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if self.projects:
            value["projects"] = ",".join(self.projects)

        if self.qualifiers:
            value["qualifiers"] = ",".join(self.qualifiers)

        return value


class SonarQubeIssueApiFilter(BaseSonarQubeApiFilter):
    assigned: Literal["yes", "no", "true", "false"] | None = Field(
        description="To retrieve assigned or unassigned issues"
    )
    assignees: list[str] | None = Field(description="List of assignees")
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
    ) = Field(
        alias="cleanCodeAttributeCategories",
        description="List of clean code attribute categories",
    )
    code_variants: list[str] | None = Field(
        alias="codeVariants", description="List of code variants"
    )
    created_before: str | None = Field(
        alias="createdBefore",
        description="To retrieve issues created before the given date",
    )
    created_after: str | None = Field(
        alias="createdAfter",
        description="To retrieve issues created after the given date",
    )
    cwe: list[str] | None = Field(description="List of CWE identifiers")
    impact_severities: list[Literal["HIGH", "LOW", "MEDIUM"]] | None = Field(
        alias="impactSeverities", description="List of impact severities"
    )
    impact_software_qualities: (
        list[Literal["MAINTAINABILITY", "RELIABILITY", "SECURITY"]] | None
    ) = Field(
        alias="impactSoftwareQualities", description="List of impact software qualities"
    )
    statuses: (
        list[Literal["OPEN", "CONFIRMED", "FALSE_POSITIVE", "ACCEPTED", "FIXED"]] | None
    ) = Field(description="List of statuses")
    languages: list[str] | None = Field(description="List of languages")
    owasp_asvs_level: Literal["1", "2", "3"] | None = Field(
        alias="owaspAsvsLevel", description="OWASP ASVS level"
    )
    resolved: Literal["yes", "no", "true", "false"] | None = Field(
        description="To retrieve resolved or unresolved issues"
    )
    rules: list[str] | None = Field(description="List of coding rule keys")
    scopes: list[Literal["MAIN", "TESTS"]] | None = Field(description="List of scopes")
    sonarsource_security: list[str] | None = Field(
        alias="sonarsourceSecurity",
        description="List of SonarSource security categories",
    )
    tags: list[str] | None = Field(description="List of tags")

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True, by_alias=True)

        for key in list(value.keys()):
            val = value[key]
            value[key] = ",".join(val) if isinstance(val, list) else val
        return value


class CustomSelector(Selector):
    def generate_request_params(self) -> dict[str, Any]:
        return {}


class SelectorWithApiFilters(CustomSelector):
    api_filters: BaseSonarQubeApiFilter | None = Field(alias="apiFilters")

    def generate_request_params(self) -> dict[str, Any]:
        if self.api_filters:
            return self.api_filters.generate_request_params()
        return super().generate_request_params()


class CustomResourceConfig(ResourceConfig):
    selector: CustomSelector
    kind: Literal[
        "analysis",
        "onprem_analysis",
        "saas_analysis",
        "portfolios",
    ]


class SonarQubeComponentProjectSelector(SelectorWithApiFilters):
    @staticmethod
    def default_metrics() -> list[str]:
        return [
            "code_smells",
            "coverage",
            "bugs",
            "vulnerabilities",
            "duplicated_files",
            "security_hotspots",
            "new_violations",
            "new_coverage",
            "new_duplicated_lines_density",
        ]

    api_filters: SonarQubeProjectApiFilter | None = Field(alias="apiFilters")
    metrics: list[str] = Field(
        description="List of metric keys", default=default_metrics()
    )


class SonarQubeProjectResourceConfig(CustomResourceConfig):
    kind: Literal["projects"]  # type: ignore
    selector: SonarQubeComponentProjectSelector


class SonarQubeGAProjectSelector(CustomSelector):
    @staticmethod
    def default_metrics() -> list[str]:
        return [
            "code_smells",
            "coverage",
            "bugs",
            "vulnerabilities",
            "duplicated_files",
            "security_hotspots",
            "new_violations",
            "new_coverage",
            "new_duplicated_lines_density",
        ]

    api_filters: SonarQubeGAProjectAPIFilter | None = Field(alias="apiFilters")

    metrics: list[str] = Field(
        description="List of metric keys", default=default_metrics()
    )


class SonarQubeGAProjectResourceConfig(CustomResourceConfig):
    kind: Literal["projects_ga"]  # type: ignore
    selector: SonarQubeGAProjectSelector


class SonarQubeIssueSelector(SelectorWithApiFilters):
    api_filters: SonarQubeIssueApiFilter | None = Field(alias="apiFilters")
    project_api_filters: SonarQubeGAProjectAPIFilter | None = Field(
        alias="projectApiFilters",
        description="Allows users to control which projects to query the issues for",
    )


class SonarQubeIssueResourceConfig(CustomResourceConfig):
    kind: Literal["issues"]  # type: ignore
    selector: SonarQubeIssueSelector


SonarResourcesConfig = Annotated[
    Union[
        SonarQubeProjectResourceConfig,
        SonarQubeIssueResourceConfig,
        SonarQubeGAProjectResourceConfig,
        CustomResourceConfig,
    ],
    Field(discriminator="kind"),
]


class SonarQubePortAppConfig(PortAppConfig):
    resources: list[SonarResourcesConfig] = Field(default_factory=list)  # type: ignore


class SonarQubeIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = SonarQubePortAppConfig
