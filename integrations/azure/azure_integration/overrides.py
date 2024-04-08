import typing

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field


class AzureSpecificKindSelector(Selector):
    api_version: str = Field(alias="apiVersion")


class AzureCloudResourceSelector(Selector):
    resource_kinds: dict[str, str] = Field(alias="resourceKinds")


class AzureSpecificKindsResourceConfig(ResourceConfig):
    selector: AzureSpecificKindSelector


class AzureCloudResourceConfig(ResourceConfig):
    kind: typing.Literal["cloudResource"]
    selector: AzureCloudResourceSelector


class AzurePortAppConfig(PortAppConfig):
    resources: list[AzureCloudResourceConfig | AzureSpecificKindsResourceConfig] = (
        Field(default_factory=list)  # type: ignore
    )
