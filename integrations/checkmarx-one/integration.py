from typing import Literal, Optional, List, Union

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field


class CheckmarxOneApiSecSelector(Selector):
    filtering: Optional[str] = Field(
        default=None,
        description="Filter API sec risks by fields",
    )
    searching: Optional[str] = Field(
        default=None,
        description="Full text search for API sec risks",
    )
    sorting: Optional[str] = Field(default=None, description="Sort API sec risks")


class CheckmarxOneProjectSelector(Selector):
    pass


class CheckmarxOneProjectResourcesConfig(ResourceConfig):
    kind: Literal["project"]
    selector: CheckmarxOneProjectSelector


class CheckmarxOneApiSecResourcesConfig(ResourceConfig):
    kind: Literal["apisec"]
    selector: CheckmarxOneApiSecSelector


class CheckmarxOneScanSelector(Selector):
    project_ids: List[str] = Field(
        default_factory=list,
        alias="projectIds",
        description="Limit search to specific project IDs",
    )


class CheckmarxOneScanResourcesConfig(ResourceConfig):
    kind: Literal["scan"]
    selector: CheckmarxOneScanSelector


class CheckmarxOnePortAppConfig(PortAppConfig):
    resources: List[
        CheckmarxOneProjectResourcesConfig
        | CheckmarxOneScanResourcesConfig
        | CheckmarxOneApiSecResourcesConfig
    ] = Field(
        default_factory=list
    )  # type: ignore


class CheckmarxOneIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = CheckmarxOnePortAppConfig
