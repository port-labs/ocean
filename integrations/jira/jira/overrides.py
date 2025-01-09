from typing import Annotated, Literal, Union

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field


class JiraIssueSelector(Selector):
    jql: str | None = None
    fields: str | None = Field(
        description="Additional fields to be included in the API response",
        default="*all",
    )


class JiraIssueConfig(ResourceConfig):
    selector: JiraIssueSelector
    kind: Literal["issue"]


class JiraProjectSelector(Selector):
    expand: str = Field(
        description="A comma-separated list of the parameters to expand.",
        default="insight",
    )


class JiraProjectResourceConfig(ResourceConfig):
    selector: JiraProjectSelector
    kind: Literal["project"]


JiraResourcesConfig = Annotated[
    Union[JiraIssueConfig, JiraProjectResourceConfig],
    Field(discriminator="kind"),
]


class JiraPortAppConfig(PortAppConfig):
    resources: list[JiraIssueConfig | JiraProjectResourceConfig | ResourceConfig]
