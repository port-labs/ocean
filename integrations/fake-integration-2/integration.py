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
    DEPARTMENT = "fake-department"
    PERSON = "fake-person"
    OFFICE = "fake-office"
    TEAM = "fake-team"
    PROJECT = "fake-project"


class FakeDepartmentResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.DEPARTMENT] = Field(
        title="Fake Department",
        description="Fake department resource kind used in Ocean core smoke tests.",
    )


class FakePersonResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.PERSON] = Field(
        title="Fake Person",
        description="Fake person resource kind used in Ocean core smoke tests.",
    )


class FakeOfficeResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.OFFICE] = Field(
        title="Fake Office",
        description="Fake office resource kind used in Ocean core smoke tests.",
    )


class FakeTeamResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.TEAM] = Field(
        title="Fake Team",
        description="Fake team resource kind used in Ocean core smoke tests.",
    )


class FakeProjectResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.PROJECT] = Field(
        title="Fake Project",
        description="Fake project resource kind used in Ocean core smoke tests.",
    )


class FakePortAppConfig(PortAppConfig):
    resources: list[
        FakeDepartmentResourceConfig
        | FakePersonResourceConfig
        | FakeOfficeResourceConfig
        | FakeTeamResourceConfig
        | FakeProjectResourceConfig
    ] = Field(
        default_factory=list,
        title="Resources",
        description="The list of resource configurations for the fake integration.",
    )  # type: ignore[assignment]


class FakeIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = FakePortAppConfig
