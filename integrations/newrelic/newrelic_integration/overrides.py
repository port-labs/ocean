from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from pydantic import BaseModel, Field


class NewRelicResourceConfig(ResourceConfig):
    class Selector(BaseModel):
        query: str
        newrelic_types: list[str] | None = Field(default=None, alias="NewRelicTypes")
        calculate_open_issue_count: bool = Field(
            default=False, alias="CalculateOpenIssueCount"
        )
        entity_query_filter: str | None = Field(default=None, alias="EntityQueryFilter")

    selector: Selector  # type: ignore


class NewRelicPortAppConfig(PortAppConfig):
    resources: list[NewRelicResourceConfig]  # type: ignore
