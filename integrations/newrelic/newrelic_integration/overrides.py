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
        title="Entity Types",
        description=(
            "List of NewRelic entity types to filter by. "
            "Example values: APM_APPLICATION, BROWSER_APPLICATION, HOST, AWSLAMBDAFUNCTION. "
            "See <a target='_blank' href='https://docs.newrelic.com/docs/new-relic-solutions/new-relic-one/core-concepts/what-entity-new-relic/#entity-type'>NewRelic entity types</a> "
            "for the full list of supported types."
        ),
    )
    calculate_open_issue_count: bool = Field(
        default=False,
        alias="calculateOpenIssueCount",
        title="Include Open Issue Count",
        description="Whether to calculate and attach the open issue count to each entity.",
    )
    entity_query_filter: str = Field(
        default="",
        alias="entityQueryFilter",
        title="Entity Query Filter",
        description=(
            "NRQL-style filter to scope which NewRelic entities are fetched. "
            "This is appended to the entity search query. "
            "Example: type in ('SERVICE','APPLICATION') "
            "See <a target='_blank' href='https://docs.newrelic.com/docs/apis/nerdgraph/examples/nerdgraph-entities-api-tutorial/#search-query'>NewRelic entity search</a> "
            "for supported filter syntax."
        ),
    )
    entity_extra_properties_query: str = Field(
        default="",
        alias="entityExtraPropertiesQuery",
        title="Additional Properties Query",
        description=(
            "Additional GraphQL inline fragment to fetch extra properties for each entity. "
            "Example: ... on ApmApplicationEntityOutline { language } "
            "See <a target='_blank' href='https://docs.newrelic.com/docs/apis/nerdgraph/examples/nerdgraph-entities-api-tutorial/'>NewRelic NerdGraph entities API</a> "
            "for supported fragment types."
        ),
    )


class NewRelicCustomResourceConfig(ResourceConfig):
    kind: str = Field(
        title="Custom Kind",
        description=(
            "Use this to map NewRelic entities by setting the kind name to any custom value "
            "(for example, 'newRelicService') and configuring selector.newRelicTypes to scope "
            "which NewRelic entity types are fetched.\n\n"
            "You can also set the kind name to the NewRelic entity type itself "
            "(for example, 'APM_APPLICATION') for a one-to-one mapping.\n\n"
            "See the <a target='_blank' href='https://docs.newrelic.com/docs/new-relic-solutions/new-relic-one/core-concepts/what-entity-new-relic/#entity-type'>"
            "NewRelic entity types reference</a> for all supported entity types."
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
        | NewRelicCustomResourceConfig
    ] = Field(
        title="Resources",
        description="List of NewRelic resources to sync into Port (alerts, service levels, alert conditions, and other NewRelic entities).",
        default_factory=list,
    )  # type: ignore[assignment]
