from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from pydantic import BaseModel


class JiraResourceConfig(ResourceConfig):
    class Selector(BaseModel):
        query: str
        jql: str | None = None

    selector: Selector  # type: ignore


class JiraPortAppConfig(PortAppConfig):
    resources: list[JiraResourceConfig]  # type: ignore
