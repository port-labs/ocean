from typing import Literal, Optional

from pydantic.v1 import Field

from confluence.helpers.utils import ObjectKind
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration

SpaceType = Literal[
    "global",
    "collaboration",
    "knowledge_base",
    "personal",
    "system",
    "onboarding",
    "xflow_sample_space",
]
SpaceStatus = Literal["current", "archived", "trashed"]
SitePermissionType = Literal["all", "none", "externalCollaborator"]


class ConfluenceSpaceSelector(Selector):
    space_type: Optional[SpaceType] = Field(
        default=None,
        alias="type",
        title="Space Type",
        description=(
            "Only sync spaces of this type. Leave empty to sync every type. "
            "Valid values: global, collaboration, knowledge_base, personal, "
            "system, onboarding, xflow_sample_space."
        ),
    )
    status: Optional[SpaceStatus] = Field(
        default=None,
        alias="status",
        title="Space Status",
        description=(
            "Only sync spaces with this status. Leave empty to sync every status. "
            "Valid values: current, archived, trashed."
        ),
    )
    labels: list[str] = Field(
        default_factory=list,
        alias="labels",
        title="Labels",
        description=(
            "Only sync spaces that have these labels. "
            "Sent to Confluence as a comma-separated list."
        ),
    )

    class Config:
        allow_population_by_field_name = True


class ConfluencePageSelector(Selector):
    include_archived: bool = Field(
        default=False,
        alias="includeArchived",
        title="Include Archived Pages",
        description=(
            "Include archived pages in addition to current pages. "
            "Deleted and trashed pages are never synced."
        ),
    )
    include_body: bool = Field(
        default=True,
        alias="includeBody",
        title="Include Page Body",
        description=(
            "Fetch each page body as markdown. On by default so the page "
            "content is in the catalog. Turn off to sync titles only. "
            "Page size drops to 25."
        ),
    )
    space_ids: list[str] = Field(
        default_factory=list,
        alias="spaceIds",
        title="Space IDs",
        description=(
            "Only sync pages in these spaces. Leave empty to sync every space. "
            "Sent to Confluence as space-id."
        ),
    )

    class Config:
        allow_population_by_field_name = True


class ConfluenceUserSelector(Selector):
    site_permission_type: SitePermissionType = Field(
        default="all",
        alias="sitePermissionType",
        title="Site Permission Type",
        description=(
            "Which users to include. all includes licensed users, external "
            "collaborators, and guests. none is licensed users only. "
            "externalCollaborator is guests and external collaborators."
        ),
    )

    class Config:
        allow_population_by_field_name = True


class ConfluenceSpaceResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.SPACE] = Field(
        title="Confluence Space",
        description="A Confluence space.",
    )
    selector: ConfluenceSpaceSelector = Field(
        title="Space Selector",
        description="Optional type, status, and label filters for Confluence spaces.",
    )


class ConfluencePageResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.PAGE] = Field(
        title="Confluence Page",
        description="A page in a Confluence space.",
    )
    selector: ConfluencePageSelector = Field(
        title="Page Selector",
        description="Filters for Confluence pages.",
    )


class ConfluenceUserResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.USER] = Field(
        title="Confluence User",
        description="A Confluence user.",
    )
    selector: ConfluenceUserSelector = Field(
        title="User Selector",
        description="Which Confluence users to sync.",
    )


class ConfluencePortAppConfig(PortAppConfig):
    resources: list[
        ConfluenceSpaceResourceConfig
        | ConfluencePageResourceConfig
        | ConfluenceUserResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]


class ConfluenceIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ConfluencePortAppConfig
