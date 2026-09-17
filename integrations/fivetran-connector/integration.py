from pydantic.v1 import Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig


class FivetranSelector(Selector):
    query: str = Field(default="true")
    function_url: str = Field(
        alias="functionUrl",
        title="Function URL",
        description="URL of the HTTP endpoint implementing the Fivetran connector protocol.",
    )
    secrets: dict[str, str] = Field(
        default_factory=dict,
        title="Secrets",
        description="Key-value string pairs forwarded to the endpoint in every request body.",
    )


class FivetranResourceConfig(ResourceConfig):
    kind: str = Field(
        title="Kind",
        description="Table name to extract from the Fivetran response insert map.",
    )
    selector: FivetranSelector


class FivetranPortAppConfig(PortAppConfig):
    resources: list[FivetranResourceConfig] = Field(default_factory=list)  # type: ignore[assignment]


class FivetranIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = FivetranPortAppConfig
