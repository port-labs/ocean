from typing import Literal
from pydantic.fields import Field

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class LaunchdarklyFeatureFlagResourceConfig(ResourceConfig):
    class LaunchdarklySelector(Selector):
        feature_flag_status: bool = Field(
            default=True,
            description="If set to true, will ingest feature flag status data to Port. Default value is true",
            alias="featureFlagStatus",
        )

    kind: Literal["flag"]
    selector: LaunchdarklySelector


class LaunchdarklyPortAppConfig(PortAppConfig):
    resources: list[LaunchdarklyFeatureFlagResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )


class LaunchdarklyIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = LaunchdarklyPortAppConfig
