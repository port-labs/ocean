import typing

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field, validator


class AzureSpecificKindSelector(Selector):
    api_version: str = Field(alias="apiVersion")


class AzureCloudResourceSelector(Selector):
    resource_kinds: dict[str, str] = Field(
        alias="resourceKinds",
    )

    @validator("resource_kinds")
    def validate_resource_kinds_min_size(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) < 1:
            raise ValueError("resourceKinds must have at least one item")
        return v


class AzureSpecificKindsResourceConfig(ResourceConfig):
    selector: AzureSpecificKindSelector


class AzureCloudResourceConfig(ResourceConfig):
    kind: typing.Literal["cloudResource"]
    selector: AzureCloudResourceSelector


class AzurePortAppConfig(PortAppConfig):
    resources: list[AzureCloudResourceConfig | AzureSpecificKindsResourceConfig] = (
        Field(default_factory=list)  # type: ignore
    )
