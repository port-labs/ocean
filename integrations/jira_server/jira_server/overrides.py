from typing import Literal

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field


class JiraIssueSelector(Selector):
    jql: str | None = None
    fields: str | None = Field(
        description="the list of fields to return for each issue. By default, all navigable fields are returned.",
        default="*all",
    )


class JiraIssueConfig(ResourceConfig):
    kind: Literal["issue"]
    selector: JiraIssueSelector


class JiraProjectSelector(Selector):
    expand: str = Field(
        default="", description="A comma-separated list of the parameters to expand"
    )


class JiraProjectConfig(ResourceConfig):
    kind: Literal["project"]
    selector: JiraProjectSelector


class JiraServerPortAppConfig(PortAppConfig):
    resources: list[JiraIssueConfig | JiraProjectConfig | ResourceConfig] = Field(
        default_factory=list
    )
