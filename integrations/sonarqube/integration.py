from abc import abstractmethod
from typing import Any, Literal, Union

from loguru import logger
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
        title="Query",
        description="Limit search to component names that contain the supplied string (e.g. 'my-service' matches 'my-service-api')",
    )
    metrics: list[dict[str, str]] | None = Field(
        title="Metrics",
        description="List of metric keys and their values such as security_rating>=2 or coverage<=80",
    )
    alert_status: str | None = Field(
        alias="alertStatus",
        title="Quality Gate Status",
        description="Filter by Quality Gate status (e.g. OK, WARN, ERROR)",
    )
    languages: Union[str, list[str]] | None = Field(
        title="Languages",
        description="Include only components whose primary language matches one of the specified values (e.g. 'java', ['python', 'js'])",
    )
    tags: Union[str, list[str]] | None = Field(
        title="Tags",
        description="Include only components that have at least one of the specified tags (e.g. 'security', ['security', 'finance'])",
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
    filter: SonarQubeComponentSearchFilter | None = Field(
        title="Component Search Filter",
        description="Criteria used to narrow which SonarQube components are retrieved, including name substring, metric thresholds, Quality Gate status, languages, and tags",
    )

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if filter := value.pop("filter", None):
            filter_instance = SonarQubeComponentSearchFilter(**filter)
            value["filter"] = filter_instance.generate_search_filters()
        if s := value.pop("s", None):
            value["s"] = s
        logger.warning(
            "The 'qualifiers' parameter has no effect on the API request "
            "and will be removed in future API requests."
        )
        return value


class SonarQubeGAProjectAPIFilter(BaseSonarQubeApiFilter):
    analyzed_before: str | None = Field(
        alias="analyzedBefore",
        title="Analyzed Before",
        description="Retrieve only projects last analyzed before this date",
    )
    on_provisioned_only: bool | None = Field(
        alias="onProvisionedOnly",
        title="Provisioned Projects",
        description="Retrieve only provisioned projects that have not yet been analyzed",
    )
    projects: list[str] | None = Field(
        title="Projects",
        description="List of project keys to include",
    )

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True)
        if self.projects:
            value["projects"] = ",".join(self.projects)

        return value


class SonarQubeIssueApiFilter(BaseSonarQubeApiFilter):
    assigned: Literal["yes", "no", "true", "false"] | None = Field(
        title="Assigned",
        description="To retrieve assigned or unassigned issues",
    )
    assignees: list[str] | None = Field(
        title="Assignees",
        description="List of assignee login names to filter by",
    )
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
        title="Clean Code Attribute Categories",
        description="Include only issues belonging to one of the specified clean code attribute categories",
    )
    code_variants: list[str] | None = Field(
        alias="codeVariants",
        title="Code Variants",
        description="Include only issues affecting one of the specified code variants (e.g. ['variant1', 'variant2'])",
    )
    created_before: str | None = Field(
        alias="createdBefore",
        title="Created Before",
        description="To retrieve issues created before the given date",
    )
    created_after: str | None = Field(
        alias="createdAfter",
        title="Created After",
        description="To retrieve issues created after the given date",
    )
    cwe: list[str] | None = Field(
        title="CWE",
        description="Include only issues mapped to one of the specified CWE identifiers (e.g. ['89', '352'])",
    )
    impact_severities: list[Literal["HIGH", "LOW", "MEDIUM"]] | None = Field(
        alias="impactSeverities",
        title="Impact Severities",
        description="Filter issues by their impact severity",
    )
    impact_software_qualities: (
        list[Literal["MAINTAINABILITY", "RELIABILITY", "SECURITY"]] | None
    ) = Field(
        alias="impactSoftwareQualities",
        title="Impact Software Qualities",
        description="Filter issues by the software quality dimension they affect",
    )
    statuses: (
        list[Literal["OPEN", "CONFIRMED", "FALSE_POSITIVE", "ACCEPTED", "FIXED"]] | None
    ) = Field(
        title="Statuses",
        description="Filter issues by their status",
    )
    languages: list[str] | None = Field(
        title="Languages",
        description="Include only issues in files written in one of the specified languages (e.g. ['java', 'python'])",
    )
    owasp_asvs_level: Literal["1", "2", "3"] | None = Field(
        alias="owaspAsvsLevel",
        title="OWASP ASVS Level",
        description="Filter issues by OWASP Application Security Verification Standard (ASVS) level",
    )
    resolved: Literal["yes", "no", "true", "false"] | None = Field(
        title="Resolved",
        description="To retrieve resolved or unresolved issues",
    )
    rules: list[str] | None = Field(
        title="Rules",
        description="Include only issues raised by one of the specified coding rule keys (e.g. ['java:S1234', 'python:S5678'])",
    )
    scopes: list[Literal["MAIN", "TESTS"]] | None = Field(
        title="Scopes",
        description="Filter by issue scope: MAIN for source code, TESTS for test code",
    )
    sonarsource_security: list[str] | None = Field(
        alias="sonarsourceSecurity",
        title="SonarSource Security",
        description="Include only issues mapped to one of the specified SonarSource security categories (e.g. ['sql-injection', 'xss'])",
    )
    tags: list[str] | None = Field(
        title="Tags",
        description="Include only issues that have at least one of the specified tags (e.g. ['security', 'performance'])",
    )

    def generate_request_params(self) -> dict[str, Any]:
        value = self.dict(exclude_none=True, by_alias=True)

        for key in list(value.keys()):
            val = value[key]
            value[key] = ",".join(val) if isinstance(val, list) else val
        return value


class CustomSelector(Selector):
    def generate_request_params(self) -> dict[str, Any]:
        return {}


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


class SonarQubeMetricsSelector(CustomSelector):
    metrics: list[str] = Field(
        default=default_metrics(),
        title="Metrics",
        description="List of metrics to retrieve",
    )


class SelectorWithApiFilters(CustomSelector):
    api_filters: BaseSonarQubeApiFilter | None = Field(
        alias="apiFilters",
        title="API Filters",
        description="Query parameters to filter the resources to retrieve",
    )

    def generate_request_params(self) -> dict[str, Any]:
        if self.api_filters:
            return self.api_filters.generate_request_params()
        return super().generate_request_params()


class CustomResourceConfig(ResourceConfig):
    selector: CustomSelector = Field(
        title="Selector",
        description="Defines which SonarQube resources to sync and how to filter them",
    )


class SonarQubeAnalysisResourceConfig(CustomResourceConfig):
    kind: Literal["analysis"] = Field(
        title="Analysis",
        description="SonarQube project analysis",
    )


class SonarQubeSaasAnalysisResourceConfig(CustomResourceConfig):
    kind: Literal["saas_analysis"] = Field(
        title="SaaS Analysis",
        description="SonarQube SaaS project analysis",
    )


class SonarQubePortfoliosResourceConfig(CustomResourceConfig):
    kind: Literal["portfolios"] = Field(
        title="Portfolios",
        description="SonarQube portfolios",
    )


class SonarQubeComponentProjectSelector(
    SonarQubeMetricsSelector, SelectorWithApiFilters
):
    api_filters: SonarQubeProjectApiFilter | None = Field(
        alias="apiFilters",
        title="API Filters",
        description="Query parameters to filter the projects to retrieve",
    )


class SonarQubeProjectResourceConfig(CustomResourceConfig):
    kind: Literal["projects"] = Field(
        title="Projects",
        description="SonarQube projects",
    )
    selector: SonarQubeComponentProjectSelector = Field(
        title="SonarQube Project Selector",
        description="Defines which SonarQube projects to sync, including which metrics and filters to apply",
    )


class SonarQubeGAProjectSelector(SonarQubeMetricsSelector):
    api_filters: SonarQubeGAProjectAPIFilter | None = Field(
        alias="apiFilters",
        title="API Filters",
        description="Query parameters to filter the projects to retrieve",
    )


class SonarQubeGAProjectResourceConfig(CustomResourceConfig):
    kind: Literal["projects_ga"] = Field(
        title="Projects (GA)",
        description="SonarQube projects using the General Availability API",
    )
    selector: SonarQubeGAProjectSelector = Field(
        title="SonarQube GA Project Selector",
        description="Defines which SonarQube projects to sync via the General Availability API, including which metrics and filters to apply",
    )


class SonarQubeIssueSelector(SelectorWithApiFilters):
    api_filters: SonarQubeIssueApiFilter | None = Field(
        alias="apiFilters",
        title="API Filters",
        description="Query parameters to filter the issues to retrieve. For example, you can use the 'assigned' parameter to retrieve only assigned or unassigned issues.",
    )
    project_api_filters: SonarQubeGAProjectAPIFilter | None = Field(
        alias="projectApiFilters",
        title="Project API Filters",
        description="Allows users to control which projects to query the issues for",
    )


class SonarQubeIssueResourceConfig(CustomResourceConfig):
    kind: Literal["issues"] = Field(
        title="Issues",
        description="SonarQube issues",
    )
    selector: SonarQubeIssueSelector = Field(
        title="SonarQube Issue Selector",
        description="Defines which SonarQube issues to sync, including issue filters and which projects to query",
    )


class SonarQubeOnPremAnalysisSelector(SonarQubeMetricsSelector): ...


class SonarQubeOnPremAnalysisResourceConfig(CustomResourceConfig):
    kind: Literal["onprem_analysis"] = Field(
        title="On-Premise Analysis",
        description="SonarQube on-premise project analysis",
    )
    selector: SonarQubeOnPremAnalysisSelector = Field(
        title="SonarQube On-Premise Analysis Selector",
        description="Defines which SonarQube on-premise project analyses to sync, including which metrics to include",
    )


class SonarQubePortAppConfig(PortAppConfig):
    resources: list[
        SonarQubeProjectResourceConfig
        | SonarQubeIssueResourceConfig
        | SonarQubeOnPremAnalysisResourceConfig
        | SonarQubeGAProjectResourceConfig
        | SonarQubeAnalysisResourceConfig
        | SonarQubeSaasAnalysisResourceConfig
        | SonarQubePortfoliosResourceConfig
    ] = Field(
        default_factory=list,
        field="Resources",
        description="Sonarqube resource mappings",
    )  # type: ignore[assignment]


class SonarQubeIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = SonarQubePortAppConfig
