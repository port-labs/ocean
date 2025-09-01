from typing import Literal, Optional, List, Union

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic import Field

from datetime import datetime, timedelta, timezone


class CheckmarxOneApiSecSelector(Selector):
    pass


class CheckmarxOneProjectSelector(Selector):
    pass


class CheckmarxOneProjectResourcesConfig(ResourceConfig):
    kind: Literal["project"]
    selector: CheckmarxOneProjectSelector


class CheckmarxOneApiSecResourcesConfig(ResourceConfig):
    kind: Literal["api-security"]
    selector: CheckmarxOneApiSecSelector


class CheckmarxOneScanSelector(Selector):
    project_names: List[str] = Field(
        default_factory=list,
        alias="projectIds",
        description="Filter scans by their project name",
    )
    branches: Optional[List[str]] = Field(
        default=None,
        description="Filter results by the name of the Git branch that was scanned.",
    )
    statuses: Optional[
        List[Literal["Queued", "Running", "Completed", "Failed", "Partial", "Canceled"]]
    ] = Field(
        default=None,
        description="Filter results by the execution status of the scans. (Case insensitive, OR operator for multiple statuses.)",
    )
    since: Optional[int] = Field(
        default=90,
        description="Filter results by the date and time when the scan was created. (UNIX timestamp in seconds)",
    )

    @property
    def from_date(self) -> Optional[str]:
        if self.since:
            return self._days_ago_to_rfc3339(self.since)
        return None

    def _days_ago_to_rfc3339(self, days: int) -> str:
        dt = datetime.now(timezone.utc) - timedelta(days=days)
        # Format to RFC3339 with microseconds and Zulu time
        # RFC3339 Date (Extend) format (e.g. 2021-06-02T12:14:18.028555Z)
        return dt.isoformat(timespec="microseconds").replace("+00:00", "Z")


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
