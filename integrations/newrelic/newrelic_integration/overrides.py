from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from pydantic import BaseModel, Field


class NewRelicResourceConfig(ResourceConfig):
    class Selector(BaseModel):
        query: str
        newrelic_types: list[str] = Field(default=None, alias="NewRelicTypes")
        relation_identifier: str = Field(default=None, alias="RelationIdentifier")
        entity_query_filter: str = Field(default=None, alias="EntityQueryFilter")

    selector: Selector


class NewRelicPortAppConfig(PortAppConfig):
    resources: list[NewRelicResourceConfig]
