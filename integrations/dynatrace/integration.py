import re
from typing import Literal

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.fields import Field


class EntityFieldsType(str):
    @classmethod
    def validate(cls, value: str) -> None:
        # Regular expression to validate the format of the aggregation value
        regex = (
            r"^(\+?(firstSeenTms|lastSeenTms|tags|fromRelationships|icon"
            r"|managementZones|properties|toRelationships|properties\.\d+)"
            r"(,\+?(firstSeenTms|lastSeenTms|tags|fromRelationships|icon|"
            r"managementZones|properties|toRelationships|properties\.\w+))*)*$"
        )
        if not re.match(regex, value):
            raise ValueError(
                "Invalid entity field format. Use 'firstSeenTms', 'lastSeenTms', 'tags', "
                "'fronRelationships', 'icon', 'managementZones', 'properties', "
                "'toRelationships', 'properties.FIELD' or comma-separated list"
                " of specified values. Values can be prefixed with '+'."
            )


class DynatraceEntitySelector(Selector):
    entity_types: list[str] = Field(
        default=["APPLICATION", "SERVICE"],
        description="List of entity types to be fetched",
        alias="entityTypes",
    )

    entity_fields: EntityFieldsType | None = Field(
        description="List of fields to include in each entity", alias="entityFields"
    )


class DynatraceResourceConfig(ResourceConfig):
    selector: DynatraceEntitySelector
    kind: Literal["entity"]


class DynatracePortAppConfig(PortAppConfig):
    resources: list[DynatraceResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )


class DynatraceIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = DynatracePortAppConfig
