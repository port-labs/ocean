from typing import ClassVar, Literal

from plain.utils import ObjectKind
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration
from pydantic.v1 import Field


class PlainSelector(Selector):
    page_size: int = Field(
        default=100,
        alias="pageSize",
        ge=1,
        le=100,
        description=(
            "Page size for list queries for this kind. "
            "Must be between 1 and 100 (Plain's maximum)."
        ),
        title="Page size",
    )


class CompanyResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.COMPANY] = Field(
        description="Plain company",
        title="Company",
    )
    selector: PlainSelector = Field(
        description="Company selector",
        title="Selector",
    )
    probe_permissions: ClassVar[tuple[str, ...]] = ("company:read",)


class TenantResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.TENANT] = Field(
        description="Plain tenant",
        title="Tenant",
    )
    selector: PlainSelector = Field(
        description="Tenant selector",
        title="Selector",
    )
    probe_permissions: ClassVar[tuple[str, ...]] = ("tenant:read",)


class UserResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.USER] = Field(
        description="Plain user",
        title="User",
    )
    selector: PlainSelector = Field(
        description="User selector",
        title="Selector",
    )
    probe_permissions: ClassVar[tuple[str, ...]] = ("user:read", "roles:read")


class MachineUserSelector(PlainSelector):
    exclude_deleted: bool = Field(
        default=False,
        alias="excludeDeleted",
        description=(
            "When true, skip deleted machine users during resync. "
            "When false (default), sync all machine users including deleted ones; "
            "use the Port query selector (e.g. isDeleted == false) to filter in Port."
        ),
        title="Exclude deleted machine users",
    )


class MachineUserResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.MACHINE_USER] = Field(
        description="Plain machine user (API bot or AI agent)",
        title="Machine user",
    )
    selector: MachineUserSelector = Field(
        description="Machine user selector",
        title="Selector",
    )
    probe_permissions: ClassVar[tuple[str, ...]] = ("machineUser:read",)


class CustomerResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.CUSTOMER] = Field(
        description="Plain customer",
        title="Customer",
    )
    selector: PlainSelector = Field(
        description="Customer selector",
        title="Selector",
    )
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "customer:read",
        "customerTenantMembership:read",
    )


class ThreadSelector(PlainSelector):
    exclude_done_threads: bool = Field(
        default=False,
        alias="excludeDoneThreads",
        description="Sync only TODO and SNOOZED threads. Leave false to sync every status.",
        title="Exclude done threads",
    )
    thread_statuses: list[str] | None = Field(
        default=None,
        alias="threadStatuses",
        description=(
            "Optional list of thread statuses to sync (TODO, SNOOZED, DONE). "
            "Ignored when excludeDoneThreads is true. Omit to sync every status."
        ),
        title="Thread statuses",
    )


class DiscussionSelector(ThreadSelector):
    exclude_ai_discussions: bool = Field(
        default=False,
        alias="excludeAiDiscussions",
        description=(
            "When true, skip AI/agent discussions (Cursor and agent-session channels) "
            "during resync. When false (default), sync every discussion including AI ones."
        ),
        title="Exclude AI discussions",
    )


class ThreadResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.THREAD] = Field(
        description="Plain thread",
        title="Thread",
    )
    selector: ThreadSelector = Field(
        description="Thread selector",
        title="Selector",
    )
    probe_permissions: ClassVar[tuple[str, ...]] = ("thread:read", "tier:read")


class ThreadMessageResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.THREAD_MESSAGE] = Field(
        description="Plain thread message",
        title="Thread message",
    )
    selector: ThreadSelector = Field(
        description="Thread message selector",
        title="Selector",
    )
    probe_permissions: ClassVar[tuple[str, ...]] = ("thread:read", "timeline:read")


class DiscussionResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.DISCUSSION] = Field(
        description="Plain thread discussion",
        title="Discussion",
    )
    selector: DiscussionSelector = Field(
        description="Discussion selector",
        title="Selector",
    )
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "thread:read",
        "threadDiscussion:read",
    )


class DiscussionMessageResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.DISCUSSION_MESSAGE] = Field(
        description="Plain discussion message",
        title="Discussion message",
    )
    selector: DiscussionSelector = Field(
        description="Discussion message selector",
        title="Selector",
    )
    probe_permissions: ClassVar[tuple[str, ...]] = (
        "thread:read",
        "threadDiscussion:read",
        "threadDiscussionMessage:read",
    )


class PlainPortAppConfig(PortAppConfig):
    resources: list[
        CompanyResourceConfig
        | TenantResourceConfig
        | UserResourceConfig
        | MachineUserResourceConfig
        | CustomerResourceConfig
        | ThreadResourceConfig
        | ThreadMessageResourceConfig
        | DiscussionResourceConfig
        | DiscussionMessageResourceConfig
    ] = Field(
        description="Resources for plain",
        title="Resources",
        default_factory=list,
    )  # type: ignore[assignment]


class PlainIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = PlainPortAppConfig
