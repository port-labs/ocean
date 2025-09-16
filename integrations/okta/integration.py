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


class OktaUserConfig(ResourceConfig):
    """Configuration for Okta users."""

    selector: OktaUserSelector
    kind: Literal["okta-user"]


class OktaGroupSelector(Selector):
    """Selector for Okta groups."""

    include_members: bool = Field(
        default=True,
        description="Include group members in the response",
    )


class OktaGroupConfig(ResourceConfig):
    """Configuration for Okta groups."""

    selector: OktaGroupSelector
    kind: Literal["okta-group"]


class OktaPortAppConfig(PortAppConfig):
    """Port app configuration for Okta integration."""

    resources: list[OktaUserConfig | OktaGroupConfig | ResourceConfig]


class OktaIntegration(BaseIntegration):
    """Okta integration class."""

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = OktaPortAppConfig
