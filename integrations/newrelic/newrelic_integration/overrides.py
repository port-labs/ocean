from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from pydantic import BaseModel


class NewRelicResourceConfig(ResourceConfig):
    class Selector(BaseModel):
        query: str
        newrelic_types: list[str] | None
        relation_identifier: str | None
        entity_query_filter: str | None

    selector: Selector


class NewRelicPortAppConfig(PortAppConfig):
    resources: list[NewRelicResourceConfig]
