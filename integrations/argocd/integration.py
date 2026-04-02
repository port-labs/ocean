from typing import Any, Optional, Literal
from misc import ResourceKindsWithSpecialHandling

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
        description="Selector to filter applications by kubernetes labels",
        alias="selector",
    )
    app_namespace: Optional[str] = Field(
        default=None,
        description="Namespace to filter applications by",
        alias="appNamespace",
    )
    projects: Optional[list[str]] = Field(
        default=None,
        description="Projects to filter applications by",
        alias="projects",
    )
    resource_version: Optional[str] = Field(
        default=None,
        description="Resource version to filter applications by",
        alias="resourceVersion",
    )
    repo: Optional[str] = Field(
        default=None,
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
        description="API query parameters to filter applications",
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
        description="API query parameters to filter applications",
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


class ArgocdPortAppConfig(PortAppConfig):
    resources: list[
        ApplicationResourceConfig | ManagedResourceResourceConfig | ResourceConfig
    ] = Field(default_factory=list)


class ArgocdIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ArgocdPortAppConfig
