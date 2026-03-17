from typing import Literal

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field, BaseModel


class AzureAPIParams(BaseModel):
    version: str = Field(
        ...,
        description="The API version to use for the resource graph",
    )


class AzureSubscriptionParams(BaseModel):
    api_params: AzureAPIParams = Field(
        default=AzureAPIParams(version="2022-12-01"),
        description="The API parameters to use for the subscription",
        alias="apiParams",
    )


class AzureResourceGraphSelector(Selector):
    graph_query: str = Field(
        ...,
        alias="graphQuery",
        description="The Resource Graph query to use for the resource graph",
    )
    api_params: AzureAPIParams = Field(
        default=AzureAPIParams(version="2024-04-01"),
        description="The API parameters to use for the resource graph",
        alias="apiParams",
    )
    subscription: AzureSubscriptionParams = Field(
        default=AzureSubscriptionParams(),
        description="The subscription to use for the resource graph",
        alias="subscription",
    )


class AzureResourceConfig(ResourceConfig):
    selector: AzureResourceGraphSelector
    kind: Literal["resource"] = Field(
        title="Azure Resource",
        description="An Azure resource queried via the Resource Graph",
    )


class AzureResourceContainerConfig(ResourceConfig):
    selector: AzureResourceGraphSelector
    kind: Literal["resourceContainer"] = Field(
        title="Azure Resource Container",
        description="An Azure resource container (e.g. subscription, resource group) queried via the Resource Graph",
    )


class AzureSubscriptionSelector(Selector, AzureSubscriptionParams): ...


class AzureSubscriptionResourceConfig(ResourceConfig):
    selector: AzureSubscriptionSelector
    kind: Literal["subscription"] = Field(
        title="Azure Subscription",
        description="An Azure subscription",
    )


class AzurePortAppConfig(PortAppConfig):
    resources: list[
        AzureResourceConfig
        | AzureResourceContainerConfig
        | AzureSubscriptionResourceConfig
    ] = Field(default_factory=list)


class AzureResourceGraphIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = AzurePortAppConfig
