from typing import Literal

from pydantic import Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig


class OktaUserSelector(Selector):
    """Selector for Okta users."""

    include_groups: bool = Field(
        default=True,
        description="Include user groups in the response",
    )
    include_applications: bool = Field(
        default=True,
        description="Include user applications in the response",
    )
    fields: str | None = Field(
        default=None,
        description="Comma-separated list of user fields to retrieve. Profile attributes should be contained within a profile:(field1,field2,...) directive. If not specified, uses default fields.",
    )


class OktaUserConfig(ResourceConfig):
    """Configuration for Okta users."""

    selector: OktaUserSelector
    kind: Literal["okta-user"]


class OktaPortAppConfig(PortAppConfig):
    """Port app configuration for Okta integration."""

    resources: list[OktaUserConfig | ResourceConfig]


class OktaIntegration(BaseIntegration):
    """Okta integration class."""

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = OktaPortAppConfig
