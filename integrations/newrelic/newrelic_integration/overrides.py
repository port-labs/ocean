from typing import Literal, ClassVar
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field


class NewRelicSelector(Selector):
    newrelic_types: list[str] | None = Field(
        default=None,
        alias="newRelicTypes",
        title="NewRelic Types",
        description="List of NewRelic entity types to filter by (e.g. APM_APPLICATION, BROWSER_APPLICATION).",
    )
    calculate_open_issue_count: bool = Field(
        default=False,
        alias="calculateOpenIssueCount",
        title="Calculate Open Issue Count",
        description="Whether to calculate and attach the open issue count to each entity.",
    )
    entity_query_filter: str = Field(
        default="",
        alias="entityQueryFilter",
        title="Entity Query Filter",
        description="NewRelic entity query filter to scope which entities are fetched.",
    )
    entity_extra_properties_query: str = Field(
        default="",
        alias="entityExtraPropertiesQuery",
        title="Entity Extra Properties Query",
        description="Additional GraphQL query fragment to fetch extra properties for each entity.",
    )


class NewRelicResourceConfig(ResourceConfig):
    kind: str = Field(
        title="Custom Kind",
        description="Use this to map NewRelic entities by setting the kind name to the NewRelic entity type.\n\nExample: APM_APPLICATION",
    )
    selector: NewRelicSelector = Field(
        title="Selector",
        description="Selector for the NewRelic entity resource.",
    )


class NewRelicAlertResourceConfig(ResourceConfig):
    kind: Literal["newRelicAlert"] = Field(
        title="NewRelic Alert",
        description="NewRelic alert resource kind.",
    )
    selector: NewRelicSelector = Field(
        title="Selector",
        description="Selector for the NewRelic alert resource.",
    )


class NewRelicServiceLevelResourceConfig(ResourceConfig):
    kind: Literal["newRelicServiceLevel"] = Field(
        title="NewRelic Service Level",
        description="NewRelic service level resource kind.",
    )
    selector: NewRelicSelector = Field(
        title="Selector",
        description="Selector for the NewRelic service level resource.",
    )


class NewRelicAlertConditionResourceConfig(ResourceConfig):
    kind: Literal["newRelicAlertCondition"] = Field(
        title="NewRelic Alert Condition",
        description="NewRelic alert condition resource kind.",
    )
    selector: NewRelicSelector = Field(
        title="Selector",
        description="Selector for the NewRelic alert condition resource.",
    )


class NewRelicPortAppConfig(PortAppConfig):
    allow_custom_kinds: ClassVar[bool] = True

    resources: list[
        NewRelicAlertResourceConfig
        | NewRelicServiceLevelResourceConfig
        | NewRelicAlertConditionResourceConfig
        | NewRelicResourceConfig
    ] = Field(
        title="Resources", default_factory=list
    )  # type: ignore[assignment]
