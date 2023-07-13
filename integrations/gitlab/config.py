from typing import List

from pydantic import Field

from port_ocean.core.handlers.port_app_config.models import PortAppConfig


class GitlabPortAppConfig(PortAppConfig):
    spec_path: str | List[str] = Field(alias="specPath", default="**/port.yml")
    branch: str = "main"
