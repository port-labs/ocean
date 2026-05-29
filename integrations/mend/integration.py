from typing import List, Literal, Optional
from enum import StrEnum

from pydantic import Field

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class ObjectKind(StrEnum):
    PROJECT = "mend-project"
    SECURITY_FINDING = "sca-finding"


class MendScaSelector(Selector):
    severity: Optional[List[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]]] = (
        Field(
            default=None,
            description="Filter security findings by severity level",
        )
    )


class MendProjectResourceConfig(ResourceConfig):
    kind: Literal["mend-project"]


class MendScaResourceConfig(ResourceConfig):
    kind: Literal["sca-finding"]
    selector: MendScaSelector


class MendPortAppConfig(PortAppConfig):
    resources: list[
        MendProjectResourceConfig | MendScaResourceConfig | ResourceConfig
    ] = Field(default_factory=list)


class MendIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = MendPortAppConfig
