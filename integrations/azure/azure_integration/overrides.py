from typing import ClassVar, Literal

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field, validator


class AzureSpecificKindSelector(Selector):
    api_version: str = Field(
        alias="apiVersion",
        title="API Version",
        description="The Azure API version to use when querying this resource kind.",
    )


class AzureCloudResourceSelector(Selector):
    resource_kinds: dict[str, str] = Field(
        alias="resourceKinds",
        title="Resource Kinds",
        description="Map of Azure resource kinds to their API versions.",
    )

    @validator("resource_kinds")
    def validate_resource_kinds_min_size(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) < 1:
            raise ValueError("resourceKinds must have at least one item")
        return v


class AzureSpecificKindsResourceConfig(ResourceConfig):
    kind: str = Field(
        title="Kind",
        description="Azure resource kind.",
    )
    selector: AzureSpecificKindSelector = Field(
        title="Selector",
        description="Selector for the Azure resource.",
    )


class AzureCloudResourceConfig(ResourceConfig):
    kind: Literal["cloudResource"] = Field(
        title="Azure Cloud Resource",
        description="Azure cloud resource kind.",
    )
    selector: AzureCloudResourceSelector = Field(
        title="Cloud Resource Selector",
        description="Selector for the Azure cloud resource.",
    )


class AzureResourceGroupResourceConfig(ResourceConfig):
    kind: Literal["Microsoft.Resources/resourceGroups"] = Field(
        title="Azure Resource Group",
        description="Azure resource group resource kind.",
    )
    selector: AzureSpecificKindSelector = Field(
        title="Resource Group Selector",
        description="Selector for the Azure resource group resource.",
    )


class AzureSubscriptionResourceConfig(ResourceConfig):
    kind: Literal["subscription"] = Field(
        title="Azure Subscription",
        description="Azure subscription resource kind.",
    )
    selector: AzureSpecificKindSelector = Field(
        title="Subscription Selector",
        description="Selector for the Azure subscription resource.",
    )


class AzurePortAppConfig(PortAppConfig):
    allow_custom_kinds: ClassVar[bool] = True

    resources: list[
        AzureResourceGroupResourceConfig
        | AzureSubscriptionResourceConfig
        | AzureCloudResourceConfig
        | AzureSpecificKindsResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore
