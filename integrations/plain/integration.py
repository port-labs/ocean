from enum import StrEnum
from typing import Literal

from plain.utils import ObjectKind
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
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


class CustomerResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.CUSTOMER] = Field(
        description="Plain customer",
        title="Customer",
    )


class ThreadSelector(Selector):
    exclude_done_threads: bool = Field(
        default=False,
        alias="excludeDoneThreads",
        description="Sync only TODO and SNOOZED threads. Leave false to sync every status.",
        title="Exclude done threads",
    )


class ThreadResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.THREAD] = Field(
        description="Plain thread",
        title="Thread",
    )
    selector: ThreadSelector = Field(
        description="Thread selector",
        title="Selector",
    )


class ThreadMessageResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.THREAD_MESSAGE] = Field(
        description="Plain thread message",
        title="Thread message",
    )
    selector: ThreadSelector = Field(
        description="Thread message selector",
        title="Selector",
    )


class PlainPortAppConfig(PortAppConfig):
    resources: list[
        ExampleKindResourceConfig
        | CompanyResourceConfig
        | TenantResourceConfig
        | UserResourceConfig
        | CustomerResourceConfig
        | ThreadResourceConfig
        | ThreadMessageResourceConfig
    ] = Field(
        description="Resources for plain",
        title="Resources",
        default_factory=list,
    )  # type: ignore[assignment]


class PlainIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = PlainPortAppConfig
