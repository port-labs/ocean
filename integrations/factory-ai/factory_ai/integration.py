from pydantic.v1 import Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)


class FactoryAIPortAppConfig(PortAppConfig):
    resources: list[ResourceConfig] = Field(
        description="Resources for factory-ai",
        title="Resources",
        default_factory=list,
    )
