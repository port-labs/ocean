from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from pydantic import BaseModel, Field


class NewRelicResourceConfig(ResourceConfig):
    class Selector(BaseModel):
        query: str
        newrelic_types: list[str] | None = Field(default=None, alias="newRelicTypes")
        calculate_open_issue_count: bool = Field(
            default=False, alias="calculateOpenIssueCount"
        )
        entity_query_filter: str = Field(default="", alias="entityQueryFilter")
        entity_extra_properties_query: str = Field(
            default="", alias="entityExtraPropertiesQuery"
        )

    selector: Selector  # type: ignore


class NewRelicPortAppConfig(PortAppConfig):
    resources: list[NewRelicResourceConfig]  # type: ignore
