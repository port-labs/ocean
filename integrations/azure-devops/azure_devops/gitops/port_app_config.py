from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from .file_entity_processor import GitSelector
from pydantic import Field
from typing import List, Literal


class GitResourceConfig(ResourceConfig):
    kind: Literal["repository"]
    selector: GitSelector


class GitPortAppConfig(PortAppConfig):
    spec_path: List[str] = Field(alias="specPath", default=["port.yml"])
    branch: str = "main"
    resources: list[GitResourceConfig | ResourceConfig] = Field(default_factory=list)  # type: ignore
