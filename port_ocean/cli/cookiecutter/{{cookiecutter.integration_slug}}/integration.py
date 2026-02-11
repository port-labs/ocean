from typing import Literal, List
from enum import StrEnum

from pydantic import Field

from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortAppConfig,
)
from port_ocean.core.integrations.base import BaseIntegration
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig


class ObjectKind(StrEnum):
    EXAMPLE_KIND = "example-kind"

class ExampleKindResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.EXAMPLE_KIND] = Field(
        description="Example kind for {{ cookiecutter.integration_slug }}",
        title="Example Kind",
    )


class {{ cookiecutter.integration_slug | to_camel }}PortAppConfig(PortAppConfig):
    resources: List[ExampleKindResourceConfig] = Field(
        default_factory=list
    )


class {{ cookiecutter.integration_slug | to_camel }}Integration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = {{ cookiecutter.integration_slug | to_camel }}PortAppConfig
