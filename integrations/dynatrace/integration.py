from typing import Literal, Annotated

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field


EntityFieldsType = Annotated[
    str,
    Field(
        pattern=(
            r"^(\+?(firstSeenTms|lastSeenTms|tags|fromRelationships|icon"
            r"|managementZones|properties|toRelationships|properties\.\d+)"
            r"(,\+?(firstSeenTms|lastSeenTms|tags|fromRelationships|icon|"
            r"managementZones|properties|toRelationships|properties\.\w+))*)*$"
        ),
        title="Entity Fields",
        description="Comma-separated list of fields to include in each entity. Values can be prefixed with '+'.",
    ),
]


class DynatraceEntitySelector(Selector):
    entity_types: list[
        Literal[
            "APPLICATION",
            "SERVICE",
        ]
    ] = Field(
        default=["APPLICATION", "SERVICE"],
        title="Entity Types",
        description="List of entity types to be fetched",
        alias="entityTypes",
    )

    entity_fields: EntityFieldsType | None = Field(
        description="List of fields to include in each entity", alias="entityFields"
    )


class SLOSelector(Selector):
    attach_related_entities: bool = Field(
        title="Attach Related Entities",
        description="Whether to attach related entities to SLO. The default is false",
        alias="attachRelatedEntities",
        default=False,
    )


class DynatraceResourceConfig(ResourceConfig):
    selector: DynatraceEntitySelector = Field(
        title="Entity Selector",
        description="Selector for the Dynatrace entity resource.",
    )
    kind: Literal["entity"] = Field(
        title="Dynatrace Entity",
        description="Dynatrace entity resource kind.",
    )


class DynatraceSLOConfig(ResourceConfig):
    selector: SLOSelector = Field(
        title="SLO Selector",
        description="Selector for the Dynatrace SLO resource.",
    )
    kind: Literal["slo"] = Field(
        title="Dynatrace SLO",
        description="Dynatrace SLO resource kind.",
    )


class DynatraceProblemResourceConfig(ResourceConfig):
    kind: Literal["problem"] = Field(
        title="Dynatrace Problem",
        description="Dynatrace problem resource kind.",
    )


class DynatraceTeamResourceConfig(ResourceConfig):
    kind: Literal["team"] = Field(
        title="Dynatrace Team",
        description="Dynatrace team resource kind.",
    )


class DynatracePortAppConfig(PortAppConfig):
    resources: list[
        DynatraceResourceConfig
        | DynatraceSLOConfig
        | DynatraceProblemResourceConfig
        | DynatraceTeamResourceConfig
    ] = Field(
        title="Resources",
        description="List of Dynatrace resources to configure for this integration.",
        default_factory=list,
    )  # type: ignore[assignment]


class DynatraceIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = DynatracePortAppConfig
