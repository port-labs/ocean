from typing import ClassVar, Literal

from pydantic import Field

from kinds import ObjectKind
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration


class ComponentResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.COMPONENT] = Field(
        title="Backstage Component",
        description="Backstage component entity kind.",
    )


class ApiResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.API] = Field(
        title="Backstage API",
        description="Backstage API entity kind.",
    )


class GroupResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.GROUP] = Field(
        title="Backstage Group",
        description="Backstage group entity kind.",
    )


class UserResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.USER] = Field(
        title="Backstage User",
        description="Backstage user entity kind.",
    )


class SystemResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.SYSTEM] = Field(
        title="Backstage System",
        description="Backstage system entity kind.",
    )


class DomainResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.DOMAIN] = Field(
        title="Backstage Domain",
        description="Backstage domain entity kind.",
    )


class ResourceEntityResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.RESOURCE] = Field(
        title="Backstage Resource",
        description="Backstage resource entity kind.",
    )


class CustomResourceConfig(ResourceConfig):
    kind: str = Field(
        title="Custom Backstage kind",
        description=(
            "Use this to ingest Backstage catalog entities whose kind is not one of the built-in options above. "
            "In Backstage, each entity has a kind string (for example built-in kinds such as Component or API, "
            "or kinds registered by plugins). The integration calls the "
            "<a target='_blank' href='https://backstage.io/docs/features/software-catalog/software-catalog-api/#get-entitiesby-query'>Get Entities by Query</a> "
            "API and filters results with a catalog filter of the form kind=your-kind, so set this field to the exact kind "
            "as stored in your software catalog."
            "\n\nExample: Template"
        ),
    )


class BackstagePortAppConfig(PortAppConfig):
    resources: list[
        ComponentResourceConfig
        | ApiResourceConfig
        | GroupResourceConfig
        | UserResourceConfig
        | SystemResourceConfig
        | DomainResourceConfig
        | ResourceEntityResourceConfig
        | CustomResourceConfig
    ] = Field(
        default_factory=list,
    )  # type: ignore[assignment]
    allow_custom_kinds: ClassVar[bool] = True


class BackstageIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = BackstagePortAppConfig
