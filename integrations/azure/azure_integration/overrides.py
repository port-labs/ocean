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


class AzureResourceConfig(ResourceConfig):
    selector: AzureSpecificKindSelector | AzureCloudResourceSelector


class AzurePortAppConfig(PortAppConfig):
    resources: list[AzureResourceConfig] = None  # type: ignore
