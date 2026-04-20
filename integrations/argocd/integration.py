from typing import Any, Optional, Literal

from misc import ObjectKind, ResourceKindsWithSpecialHandling

from pydantic import BaseModel, Field

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class ApplicationQueryParams(BaseModel):
    selector: Optional[str] = Field(
        default=None,
        title="Kubernetes labels",
        description=(
            "Passes through to the Argo CD Applications API as a Kubernetes label selector. "
            "Use multiple selectors as a comma-separated list (e.g. `env=prod,tier=web`)."
        ),
        alias="selector",
    )
    app_namespace: Optional[str] = Field(
        default=None,
        title="Application Namespace",
        description="Namespace to filter applications by",
        alias="appNamespace",
    )
    projects: Optional[list[str]] = Field(
        default=None,
        title="Projects",
        description="Projects to filter applications by",
        alias="projects",
    )
    resource_version: Optional[str] = Field(
        default=None,
        title="Resource Version",
        description="Resource version to filter applications by",
        alias="resourceVersion",
    )
    repo: Optional[str] = Field(
        default=None,
        title="Repository",
        description="Repository to filter applications by",
        alias="repo",
    )

    @property
    def generate_request_params(self) -> dict[str, Any]:
        return self.dict(exclude_none=True)


class ApplicationSelector(Selector):
    query_params: Optional[ApplicationQueryParams] = Field(
        default=None,
        alias="queryParams",
        title="Application Query Params",
        description="API query parameters to filter applications by",
    )


class ApplicationResourceConfig(ResourceConfig):
    kind: Literal[ResourceKindsWithSpecialHandling.APPLICATION] = Field(
        title="Application",
        description="Application resource kind.",
    )
    selector: ApplicationSelector = Field(
        title="Application selector",
        description="Selector for the application resource.",
    )


class ManagedResourceSelector(Selector):
    app_filters: Optional[ApplicationQueryParams] = Field(
        default=None,
        alias="appFilters",
        title="Application Query Params",
        description="API query parameters to filter applications by",
    )


class ManagedResourceResourceConfig(ResourceConfig):
    kind: Literal[ResourceKindsWithSpecialHandling.MANAGED_RESOURCE] = Field(
        title="Managed resource",
        description="Managed resource kind.",
    )
    selector: ManagedResourceSelector = Field(
        title="Managed resource selector",
        description="Selector for the managed resource resource.",
    )


class ProjectResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.PROJECT] = Field(
        title="Argo CD Project",
        description="Argo CD project resource kind.",
    )


class ClusterResourceConfig(ResourceConfig):
    kind: Literal[ResourceKindsWithSpecialHandling.CLUSTER] = Field(
        title="Argo CD Cluster",
        description="Argo CD cluster resource kind.",
    )


class DeploymentHistoryResourceConfig(ResourceConfig):
    kind: Literal[ResourceKindsWithSpecialHandling.DEPLOYMENT_HISTORY] = Field(
        title="Argo CD Deployment History",
        description="Argo CD deployment history resource kind.",
    )


class KubernetesResourceResourceConfig(ResourceConfig):
    kind: Literal[ResourceKindsWithSpecialHandling.KUBERNETES_RESOURCE] = Field(
        title="Argo CD Kubernetes Resource",
        description="Argo CD kubernetes resource kind.",
    )


class ArgocdPortAppConfig(PortAppConfig):
    resources: list[
        ApplicationResourceConfig
        | ManagedResourceResourceConfig
        | ProjectResourceConfig
        | ClusterResourceConfig
        | DeploymentHistoryResourceConfig
        | KubernetesResourceResourceConfig
    ] = Field(
        default_factory=list,
    )  # type: ignore[assignment]


class ArgocdIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ArgocdPortAppConfig
