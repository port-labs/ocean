from typing import Optional
from pydantic import BaseModel
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector
)


class OktaUserSelector(Selector):
    """Selector for Okta users"""
    filter: Optional[str] = None
    limit: Optional[int] = None


class OktaGroupSelector(Selector):
    """Selector for Okta groups"""
    filter: Optional[str] = None
    limit: Optional[int] = None
    expand: Optional[str] = None
    include_members: Optional[bool] = False


class OktaRoleSelector(Selector):
    """Selector for Okta roles"""
    filter: Optional[str] = None
    limit: Optional[int] = None


class OktaPermissionSelector(Selector):
    """Selector for Okta permissions"""
    filter: Optional[str] = None
    limit: Optional[int] = None


class OktaApplicationSelector(Selector):
    """Selector for Okta applications"""
    filter: Optional[str] = None
    limit: Optional[int] = None


class OktaUserResourceConfig(ResourceConfig):
    """Resource config for Okta users"""
    kind: str = "oktaUser"
    selector: OktaUserSelector


class OktaGroupResourceConfig(ResourceConfig):
    """Resource config for Okta groups"""
    kind: str = "oktaGroup"
    selector: OktaGroupSelector


class OktaRoleResourceConfig(ResourceConfig):
    """Resource config for Okta roles"""
    kind: str = "oktaRole"
    selector: OktaRoleSelector


class OktaPermissionResourceConfig(ResourceConfig):
    """Resource config for Okta permissions"""
    kind: str = "oktaPermission"
    selector: OktaPermissionSelector


class OktaApplicationResourceConfig(ResourceConfig):
    """Resource config for Okta applications"""
    kind: str = "oktaApplication"
    selector: OktaApplicationSelector


class OktaPortAppConfig(PortAppConfig):
    """Port app configuration for Okta integration"""
    
    class Config:
        extra = "allow"