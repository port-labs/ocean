from pydantic.fields import Field
from typing import Literal
from enum import StrEnum


from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration


class ObjectKind(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"
    PROJECT_TAG = "project-tag"
    ISSUE_TAG = "issue-tag"
    USER = "user"
    TEAM = "team"


class SentrySelector(Selector):
    tag: str | None = Field(
        default="environment",
        alias="tag",
        title="Tag",
        description="The name of the tag used to filter the resources. The default value is environment",
    )


class UserResourceConfig(ResourceConfig):
    kind: Literal["user"] = Field(
        title="Sentry User",
        description="Sentry user resource kind.",
    )


class TeamSelector(Selector):
    include_members: bool = Field(
        alias="includeMembers",
        default=False,
        title="Include Members",
        description="Whether to include the members of the team, defaults to false",
    )


class IssueSelector(SentrySelector):
    include_archived: bool = Field(
        alias="includeArchived",
        default=True,
        title="Include Archived",
        description="Whether to include the archived issues, defaults to true",
    )


class SentryResourceConfig(ResourceConfig):
    selector: SentrySelector = Field(
        title="Sentry Selector",
        description="Selector for the Sentry project or project-tag resource.",
    )
    kind: Literal["project"] = Field(
        title="Sentry Project",
        description="Sentry project resource kind.",
    )


class SentryProjectTagResourceConfig(ResourceConfig):
    selector: SentrySelector = Field(
        title="Sentry Project Tag Selector",
        description="Selector for the Sentry project-tag resource.",
    )
    kind: Literal["project-tag"] = Field(
        title="Sentry Project Tag",
        description="Sentry project tag resource kind.",
    )


class TeamResourceConfig(ResourceConfig):
    kind: Literal["team"] = Field(
        title="Sentry Team",
        description="Sentry team resource kind.",
    )
    selector: TeamSelector = Field(
        title="Team Selector",
        description="Selector for the Sentry team resource.",
    )


class IssueResourceConfig(ResourceConfig):
    kind: Literal["issue"] = Field(
        title="Sentry Issue",
        description="Sentry issue resource kind.",
    )
    selector: IssueSelector = Field(
        title="Issue Selector",
        description="Selector for the Sentry issue resource.",
    )


class IssueTagResourceConfig(ResourceConfig):
    kind: Literal["issue-tag"] = Field(
        title="Sentry Issue Tag",
        description="Sentry issue tag resource kind.",
    )
    selector: IssueSelector = Field(
        title="Issue Tag Selector",
        description="Selector for the Sentry issue-tag resource.",
    )


class SentryPortAppConfig(PortAppConfig):
    resources: list[
        SentryResourceConfig
        | SentryProjectTagResourceConfig
        | TeamResourceConfig
        | UserResourceConfig
        | IssueResourceConfig
        | IssueTagResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]


class SentryIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = SentryPortAppConfig
