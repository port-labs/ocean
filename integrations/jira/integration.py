from typing import Literal

from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.fields import Field


class JiraIssueSelector(Selector):
    jql: str | None = Field(
        description="Jira Query Language (JQL) query to filter issues",
    )
    fields: str | None = Field(
        description="Additional fields to be included in the API response",
        default="*all",
    )


class JiraIssueResourceConfig(ResourceConfig):
    kind: Literal["issue"]
    selector: JiraIssueSelector


class JiraPortAppConfig(PortAppConfig):
    resources: list[JiraIssueResourceConfig | ResourceConfig] = Field(
        default_factory=list
    )


class JiraIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = JiraPortAppConfig
