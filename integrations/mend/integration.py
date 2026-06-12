from typing import List, Literal, Optional

from pydantic import Field

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class MendScaSelector(Selector):
    severity: Optional[List[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]]] = Field(
        default=None,
        title="Severity",
        description="Filter security findings by severity level. Accepted values: CRITICAL, HIGH, MEDIUM, LOW.",
    )


class MendProjectResourceConfig(ResourceConfig):
    kind: Literal["mend-project"] = Field(
        title="Mend Project",
        description="Mend.io project resource kind.",
    )


class MendScaResourceConfig(ResourceConfig):
    kind: Literal["sca-finding"] = Field(
        title="SCA Finding",
        description="Mend.io SCA security finding resource kind.",
    )
    selector: MendScaSelector = Field(
        title="SCA Finding Selector",
        description="Selector for filtering SCA security findings.",
    )


class MendPortAppConfig(PortAppConfig):
    resources: list[MendProjectResourceConfig | MendScaResourceConfig] = Field(
        default_factory=list,
        title="Resources",
        description="List of Mend.io resource kinds to sync into Port.",
    )  # type: ignore[assignment]


class MendIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = MendPortAppConfig
