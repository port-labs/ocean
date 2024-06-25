from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
    Selector,
)
from pydantic import Field


class AWSDescribeResourcesSelector(Selector):
    use_get_resource_api: bool = Field(alias="useGetResourceAPI", default=False)


class AWSResourceConfig(ResourceConfig):
    selector: AWSDescribeResourcesSelector


class AWSPortAppConfig(PortAppConfig):
    resources: list[AWSResourceConfig] = Field(default_factory=list)  # type: ignore
