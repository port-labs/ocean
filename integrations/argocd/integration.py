from typing import Any, Optional, Literal
from enum import StrEnum

from pydantic import Field

from port_ocean.core.handlers import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class ObjectKind(StrEnum):
    PROJECT = "project"
    APPLICATION = "application"


class ResourceKindsWithSpecialHandling(StrEnum):
    DEPLOYMENT_HISTORY = "deployment-history"
    KUBERNETES_RESOURCE = "kubernetes-resource"
    MANAGED_RESOURCE = "managed-resource"
    CLUSTER = "cluster"


class ApplicationSelector(Selector):
    query_params: Optional[dict[str, Any]] = Field(
        default=None,
        alias="queryParams",
        description="API query parameters to filter applications",
    )


class ApplicationResourceConfig(ResourceConfig):
    kind: Literal["application"]
    selector: ApplicationSelector


class ArgocdPortAppConfig(PortAppConfig):
    resources: list[ApplicationResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )


class ArgocdIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ArgocdPortAppConfig
