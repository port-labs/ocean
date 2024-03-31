from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field


class AzureSelector(Selector):
    api_version: str | None = Field(alias="apiVersion", default=None)
    resource_kinds: dict[str, str] | None = Field(alias="resourceKinds", default=None)


class AzureResourceConfig(ResourceConfig):
    selector: AzureSelector


class AzurePortAppConfig(PortAppConfig):
    resources: list[AzureResourceConfig] = None  # type: ignore
