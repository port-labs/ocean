from typing import Literal

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from pydantic import Field


class ZendeskTicketSelector(Selector):
    status: str | None = Field(
        description="Filter tickets by status (e.g., 'new', 'open', 'pending', 'hold', 'solved', 'closed')",
        default=None,
    )
    priority: str | None = Field(
        description="Filter tickets by priority (e.g., 'low', 'normal', 'high', 'urgent')",
        default=None,
    )
    assignee_id: int | None = Field(
        alias="assigneeId",
        description="Filter tickets by assignee user ID",
        default=None,
    )
    organization_id: int | None = Field(
        alias="organizationId",
        description="Filter tickets by organization ID",
        default=None,
    )


class ZendeskTicketResourceConfig(ResourceConfig):
    kind: Literal["ticket"]
    selector: ZendeskTicketSelector


class ZendeskUserSelector(Selector):
    role: str | None = Field(
        description="Filter users by role (e.g., 'end-user', 'agent', 'admin')",
        default=None,
    )
    organization_id: int | None = Field(
        alias="organizationId",
        description="Filter users by organization ID",
        default=None,
    )


class ZendeskUserResourceConfig(ResourceConfig):
    kind: Literal["user"]
    selector: ZendeskUserSelector


class ZendeskOrganizationSelector(Selector):
    external_id: str | None = Field(
        alias="externalId",
        description="Filter organizations by external ID",
        default=None,
    )


class ZendeskOrganizationResourceConfig(ResourceConfig):
    kind: Literal["organization"]
    selector: ZendeskOrganizationSelector


class ZendeskGroupSelector(Selector):
    include_deleted: bool = Field(
        alias="includeDeleted",
        description="Whether to include deleted groups",
        default=False,
    )


class ZendeskGroupResourceConfig(ResourceConfig):
    kind: Literal["group"]
    selector: ZendeskGroupSelector


class ZendeskBrandSelector(Selector):
    active_only: bool = Field(
        alias="activeOnly",
        description="Only fetch active brands",
        default=True,
    )


class ZendeskBrandResourceConfig(ResourceConfig):
    kind: Literal["brand"]
    selector: ZendeskBrandSelector


class ZendeskPortAppConfig(PortAppConfig):
    resources: list[
        ZendeskTicketResourceConfig
        | ZendeskUserResourceConfig
        | ZendeskOrganizationResourceConfig
        | ZendeskGroupResourceConfig
        | ZendeskBrandResourceConfig
        | ResourceConfig
    ]