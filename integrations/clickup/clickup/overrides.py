from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from pydantic import BaseModel


class ClickUpResourceConfig(ResourceConfig):
    class Selector(BaseModel):
        query: str
        jql: str | None = None

    selector: Selector  # type: ignore


class ClickUpPortAppConfig(PortAppConfig):
    resources: list[ClickUpResourceConfig]  # type: ignore
