from typing import Optional
from pydantic import BaseModel
from port_ocean.core.handlers.port_app_config.models import PortAppConfig


class HarborConfig(BaseModel):
    """Configuration for Harbor integration"""

    harbor_url: str
    username: str
    password: str
    project_name_prefix: Optional[str] = None
    verify_ssl: bool = False
    include_public_projects: bool = True
    include_private_projects: bool = True
    min_severity: Optional[str] = None
    webhook_secret: Optional[str] = None


class HarborPortAppConfig(PortAppConfig):
    """Port app config for Harbor integration"""

    harbor: HarborConfig
