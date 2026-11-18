from enum import StrEnum
from typing import Literal

from pydantic.v1 import Field

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration


class ObjectKind(StrEnum):
    DUMMY = "dummy-kind"


class DummyKindResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.DUMMY] = Field(
        title="Dummy Kind",
        description="Dummy resource kind used to trigger Wiz image scans.",
    )


class DummyWizScanPortAppConfig(PortAppConfig):
    resources: list[DummyKindResourceConfig] = Field(
        default_factory=list,
        title="Resources",
        description="The list of resource configurations for the dummy Wiz scan integration.",
    )  # type: ignore[assignment]


class DummyWizScanIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = DummyWizScanPortAppConfig
