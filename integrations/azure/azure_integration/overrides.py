from port_ocean.core.handlers.port_app_config.models import (
    BaseModel,
    ResourceConfig,
    PortAppConfig,
)


class AzureResourceConfig(ResourceConfig):
    class Selector(BaseModel):
        query: str = None
        api_version: str

    selector: Selector


class AzurePortAppConfig(PortAppConfig):
    resources: list[AzureResourceConfig] = None
