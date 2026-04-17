from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import BaseModel, Field
from typing import Any, Literal, Optional
from port_ocean.core.integrations.base import BaseIntegration


class GenerateQueryParamMixin(BaseModel):
    def generate_query_params(self) -> dict[str, Any]:
        params = self.dict(exclude_none=True, exclude_unset=True)
        return params

    def merge_with(self, other: dict[str, Any]) -> dict[str, Any]:
        query_params = self.generate_query_params()
        return {**other, **query_params}


class SnykProjectAPIQueryParams(GenerateQueryParamMixin):
    target_id: Optional[list[str]] = Field(
        default=None,
        title="Target IDs",
        description="Only return projects in the provided targets",
    )
    target_reference: Optional[str] = Field(
        default=None,
        title="Target Reference",
        description="Return projects that match the provided target reference",
    )
    target_file: Optional[str] = Field(
        default=None,
        title="Target File",
        description="Return projects that match the provided target file",
    )
    target_runtime: Optional[str] = Field(
        default=None,
        title="Target Runtime",
        description="Return projects that match the provided target runtime",
    )
    names: Optional[list[str]] = Field(
        default=None,
        title="Names",
        description="Return projects that match the provided names",
    )
    names_start_with: Optional[list[str]] = Field(
        default=None,
        title="Names start with",
        description="Return projects with names starting with the specified prefix.",
    )
    origins: Optional[list[str]] = Field(
        default=None,
        title="Origins",
        description="Return projects that match the provided origins.",
    )

    types: Optional[list[str]] = Field(
        default=None,
        title="Types",
        description="Return projects of the provided type (e.g. npm, pip, docker)",
    )
    tags: Optional[list[str]] = Field(
        default=None,
        title="Tags",
        description="Return projects that match all the provided tags (key=value format)",
    )
    business_criticality: Optional[
        list[Literal["critical", "high", "medium", "low"]]
    ] = Field(
        default=None,
        title="Business Criticality",
        description="Return projects with the provided business criticality",
    )
    environment: Optional[
        list[
            Literal[
                "frontend",
                "backend",
                "internal",
                "external",
                "mobile",
                "saas",
                "onprem",
                "hosted",
                "distributed",
            ]
        ]
    ] = Field(
        default=None,
        title="Environment",
        description="Return projects with the provided environment",
    )
    lifecycle: Optional[list[Literal["production", "development", "sandbox"]]] = Field(
        default=None,
        title="Lifecycle",
        description="Return projects with the provided lifecycle",
    )
    ids: Optional[list[str]] = Field(
        default=None,
        title="Project IDs",
        description="Return only projects with the provided IDs",
    )


class SnykVulnerabilityAPIQueryParams(GenerateQueryParamMixin):
    type: Optional[
        Literal[
            "package", "vulnerability", "license", "cloud", "code", "custom", "config"
        ]
    ] = Field(default=None, title="Type", description="The type of an issue.")
    updated_before: Optional[str] = Field(
        default=None,
        title="Updated Before",
        description="Return issues last updated before this date. Must be RFC3339 with timezone (e.g. 2021-05-29T09:50:54Z).",
        regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$",
    )
    updated_after: Optional[str] = Field(
        default=None,
        title="Updated After",
        description="Return issues last updated after this date. Must be RFC3339 with timezone (e.g. 2021-05-29T09:50:54Z).",
        regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$",
    )
    created_before: Optional[str] = Field(
        default=None,
        title="Created Before",
        description="Return issues created before this date. Must be RFC3339 with timezone (e.g. 2021-05-29T09:50:54Z).",
        regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$",
    )
    created_after: Optional[str] = Field(
        default=None,
        title="Created After",
        description="Return issues created after this date. Must be RFC3339 with timezone (e.g. 2021-05-29T09:50:54Z).",
        regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$",
    )
    effective_severity_level: Optional[
        list[Literal["info", "low", "medium", "high", "critical"]]
    ] = Field(
        default=None,
        title="Effective Severity Level",
        description="A filter to select issues with the provided effective severity level.",
    )
    status: Optional[list[Literal["open", "resolved"]]] = Field(
        default=None,
        title="Status",
        description="A filter to select issues with the provided status.",
    )
    ignored: Optional[bool] = Field(
        default=None,
        title="Ignored Issues Only",
        description="When true, return only ignored issues. When false, return only non-ignored issues. Omit to return all.",
    )


class ProjectSelector(Selector):
    attach_issues_to_project: bool = Field(
        alias="attachIssuesToProject",
        default=True,
        title="Attach Issues to Project",
        description="Whether to attach issues to the project during ingestion.",
    )
    api_query_params: Optional[SnykProjectAPIQueryParams] = Field(
        alias="apiQueryParams",
        default=None,
        title="API Query Params",
        description="Snyk project API query params, for more information please look at the <a href='https://docs.snyk.io/snyk-api/reference/projects' target='_blank'>Snyk API docs</a>",
    )


class VulnerabilitySelector(Selector):
    api_query_params: Optional[SnykVulnerabilityAPIQueryParams] = Field(
        alias="apiQueryParams",
        default=None,
        title="API Query Params",
        description="Snyk issue API query params, for more information please look at the <a href='https://docs.snyk.io/snyk-api/reference/issues#get-orgs-org_id-issues'>API docs </a>",
    )
    project_query_params: Optional[SnykProjectAPIQueryParams] = Field(
        alias="projectQueryParams",
        default=None,
        title="Project Query Params",
        description="Filters the projects whose issues are ingested. When omitted, issues from all projects are returned.",
    )
    enrich_with_project: bool = Field(
        default=False,
        title="Enrich with Project",
        alias="enrichWithProject",
        description="Enrich each vulnerability with its associated project data. For large orgs this is API and memory intensive — use projectQueryParams to limit scope.",
    )


class ProjectResourceConfig(ResourceConfig):
    kind: Literal["project"] = Field(
        title="Snyk Project",
        description="Snyk project resource kind.",
    )
    selector: ProjectSelector = Field(
        title="Project Selector",
        description="Selector for the Snyk project resource.",
    )


class TargetSelector(Selector):
    attach_project_data: bool = Field(
        default=True,
        alias="attachProjectData",
        title="Attach Project Data",
        description="Whether to attach project data to the target during ingestion.",
    )


class TargetResourceConfig(ResourceConfig):
    kind: Literal["target"] = Field(
        title="Snyk Target",
        description="Snyk target resource kind.",
    )
    selector: TargetSelector = Field(
        title="Target Selector",
        description="Selector for the Snyk target resource.",
    )


class OrganizationResourceConfig(ResourceConfig):
    kind: Literal["organization"] = Field(
        title="Snyk Organization",
        description="Snyk organization resource kind.",
    )


class VulnerabilityResourceConfig(ResourceConfig):
    kind: Literal["vulnerability"] = Field(
        title="Snyk Vulnerability",
        description="Snyk vulnerability resource kind.",
    )
    selector: VulnerabilitySelector = Field(
        title="Vulnerability Selector",
        description="Selector to filter Snyk Vulnerabilities",
    )


class IssueResourceConfig(ResourceConfig):
    kind: Literal["issue"] = Field(
        title="Snyk Issue",
        description="Snyk issue resource kind.",
    )


class SnykPortAppConfig(PortAppConfig):
    resources: list[
        ProjectResourceConfig
        | TargetResourceConfig
        | OrganizationResourceConfig
        | VulnerabilityResourceConfig
        | IssueResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]


class SnykIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = SnykPortAppConfig
