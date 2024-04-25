from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field

class AWSSelector(Selector):
    resource_kinds: list[str] = Field(alias="resourceKinds", default=[], min_items=1)


class AWSResourceConfig(ResourceConfig):
    selector: AWSSelector | None = None

class AWSPortAppConfig(PortAppConfig):
    resources: list[AWSResourceConfig] = []