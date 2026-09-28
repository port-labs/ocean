from enum import StrEnum
from typing import Literal

from plain.utils import ObjectKind
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.v1 import Field


class ExampleKind(StrEnum):
    EXAMPLE_KIND = "example-kind"


class ExampleKindResourceConfig(ResourceConfig):
    kind: Literal[ExampleKind.EXAMPLE_KIND] = Field(
        description="Example kind for plain",
        title="Example Kind",
    )


class CompanyResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.COMPANY] = Field(
        description="Plain company",
        title="Company",
    )


class TenantResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.TENANT] = Field(
        description="Plain tenant",
        title="Tenant",
    )


class UserResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.USER] = Field(
        description="Plain user",
        title="User",
    )


class PlainPortAppConfig(PortAppConfig):
    resources: list[
        ExampleKindResourceConfig
        | CompanyResourceConfig
        | TenantResourceConfig
        | UserResourceConfig
    ] = Field(
        description="Resources for plain",
        title="Resources",
        default_factory=list,
    )  # type: ignore[assignment]


class PlainIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = PlainPortAppConfig
