from typing import Literal

from pydantic import Field

from armorcode.helpers.utils import ObjectKind
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration


class ProductResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.PRODUCT] = Field(
        title="Armorcode Product",
        description="Armorcode product resource kind.",
    )


class SubProductResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.SUB_PRODUCT] = Field(
        title="Armorcode Sub-Product",
        description="Armorcode sub-product resource kind.",
    )


class FindingResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.FINDING] = Field(
        title="Armorcode Finding",
        description="Armorcode finding resource kind.",
    )


class ArmorcodePortAppConfig(PortAppConfig):
    resources: list[
        ProductResourceConfig | SubProductResourceConfig | FindingResourceConfig
    ] = Field(
        default_factory=list,
    )  # type: ignore[assignment]


class ArmorcodeIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ArmorcodePortAppConfig
