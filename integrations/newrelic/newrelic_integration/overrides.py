from port_ocean.core.handlers.port_app_config.models import (
    BaseModel,
    ResourceConfig,
    PortAppConfig,
)


class NewRelicResourceConfig(ResourceConfig):
    class Selector(BaseModel):
        query: str
        newrelic_types: list = None
        relation_identifier: str = None
        entity_query_filter: str = None

    selector: Selector


class NewRelicPortAppConfig(PortAppConfig):
    resources: list[NewRelicResourceConfig]
