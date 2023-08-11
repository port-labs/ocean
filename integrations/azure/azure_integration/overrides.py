from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
)
from pydantic import BaseModel, Field


class AzureResourceConfig(ResourceConfig):
    class Selector(BaseModel):
        query: str
        api_version: str = Field(..., alias="apiVersion")

    selector: Selector  # type: ignore


class AzurePortAppConfig(PortAppConfig):
    resources: list[AzureResourceConfig] = None  # type: ignore
