from typing import Optional
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from pydantic import BaseModel, Field


class GitLabResourceConfig(ResourceConfig):
    class Selector(BaseModel):
        query: str
        gitlab_types: list[str] | None = Field(default=None, alias="GitLabTypes")
        owned: Optional[bool] = Field(default=True, alias="Owned")
        visibility: Optional[str] | None = Field(default=None, alias="Visibility")

    selector: Selector  # type: ignore
