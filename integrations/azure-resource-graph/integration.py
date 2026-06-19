from typing import Any, Literal

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
        title="Version",
        description="The API version to use for the resource graph",
    )


class AzureSubscriptionParams(BaseModel):
    api_params: AzureAPIParams = Field(
        title="API Params",
        default=AzureAPIParams(version="2022-12-01"),
        description="The API parameters to use for the subscription",
        alias="apiParams",
    )


class AzureResourceGraphSelector(Selector):
    graph_query: str = Field(
        ...,
        title="Kusto Graph Query",
        alias="graphQuery",
        description="Use this to map Azure Resource Graph data by setting the table name to a supported <a target='_blank' href='https://learn.microsoft.com/en-us/azure/governance/resource-graph/reference/supported-tables-resources'>Azure Resource Graph table</a>",
    )
    api_params: AzureAPIParams = Field(
        title="API Params",
        default=AzureAPIParams(version="2024-04-01"),
        description="The API parameters to use for the resource graph",
        alias="apiParams",
    )
    subscription: AzureSubscriptionParams = Field(
        title="Subscription",
        default=AzureSubscriptionParams(),
        description="The subscription to use for the resource graph",
        alias="subscription",
    )

    class Config:
        @staticmethod
        def schema_extra(schema: dict[Any, Any], model: type) -> None:
            props = schema.get("properties", {})
            if "subscription" in props:
                props["subscription"]["default"] = {
                    "apiParams": {"version": "2022-12-01"}
                }


class AzureResourceGraphConfig(ResourceConfig):
    selector: AzureResourceGraphSelector = Field(
        title="Azure Resource Selector",
        description="Selects Azure resources to query via the Resource Graph",
    )
    kind: Literal["resource"] = Field(
        title="Azure Resource",
        description="An Azure resource queried via the Resource Graph",
    )


class AzureResourceContainerConfig(ResourceConfig):
    selector: AzureResourceGraphSelector = Field(
        title="Azure Resource Container Selector",
        description="Selects Azure resource containers to query via the Resource Graph",
    )
    kind: Literal["resourceContainer"] = Field(
        title="Azure Resource Container",
        description="An Azure resource container (e.g. subscription, resource group) queried via the Resource Graph",
    )


class AzureSubscriptionSelector(Selector, AzureSubscriptionParams): ...


class AzureSubscriptionResourceConfig(ResourceConfig):
    selector: AzureSubscriptionSelector = Field(
        title="Azure Subscription Selector",
        description="Selects Azure subscriptions to query via the Resource Graph",
    )
    kind: Literal["subscription"] = Field(
        title="Azure Subscription",
        description="An Azure subscription",
    )


class AzurePortAppConfig(PortAppConfig):
    resources: list[
        AzureResourceGraphConfig
        | AzureResourceContainerConfig
        | AzureSubscriptionResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]


class AzureResourceGraphIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = AzurePortAppConfig
