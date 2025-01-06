from typing import Annotated, Literal, Union

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field


class JiraIssueSelector(Selector):
    jql: str | None = None


class JiraResourceConfig(ResourceConfig):
    selector: JiraIssueSelector
    kind: Literal["issue", "user"]


class JiraProjectSelector(Selector):
    expand: str = Field(
        description="A comma-separated list of the parameters to expand.",
        default="insight",
    )


class JiraProjectResourceConfig(ResourceConfig):
    selector: JiraProjectSelector
    kind: Literal["project"]


JiraResourcesConfig = Annotated[
    Union[
        JiraResourceConfig,
        JiraProjectResourceConfig,
    ],
    Field(discriminator="kind"),
]


class JiraPortAppConfig(PortAppConfig):
    resources: list[JiraResourceConfig | JiraProjectResourceConfig]  # type: ignore
