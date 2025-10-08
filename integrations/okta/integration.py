from typing import Literal

from pydantic import Field
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig


def get_default_user_fields() -> str:
    """Default list of fields to fetch for users.

    Matches previous behavior from okta.core.options.get_default_user_fields.
    """
    return (
        "id,status,created,activated,lastLogin,lastUpdated,"
        "profile:(login,firstName,lastName,displayName,email,title,department,"
        "employeeNumber,mobilePhone,primaryPhone,streetAddress,city,state,zipCode,countryCode)"
    )


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
    fields: str = Field(
        default_factory=get_default_user_fields,
        description="Comma-separated list of user fields to retrieve. Profile attributes should be contained within a profile:(field1,field2,...) directive.",
    )


class OktaUserConfig(ResourceConfig):
    """Configuration for Okta users."""

    selector: OktaUserSelector
    kind: Literal["okta-user"]


class OktaPortAppConfig(PortAppConfig):
    """Port app configuration for Okta integration."""

    resources: list[OktaUserConfig | ResourceConfig] = Field(
        default_factory=list,
        description="Specify the resources to include in the sync",
    )


class OktaIntegration(BaseIntegration):
    """Okta integration class."""

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = OktaPortAppConfig
