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
        description=(
            "Port resource kind name to use for NewRelic entities. This can be any custom kind "
            '(for example, "newRelicService") and may map to one or more NewRelic entity types '
            "configured via selector.newRelicTypes.\n\n"
            "If you prefer a separate Port kind per NewRelic entity type, you can also set the "
            'kind name to the NewRelic entity type itself (for example, "APM_APPLICATION").'
        ),
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
        title="Resources",
        description="List of NewRelic resources to sync into Port (alerts, service levels, alert conditions, and other NewRelic entities).",
        default_factory=list,
    )  # type: ignore[assignment]
