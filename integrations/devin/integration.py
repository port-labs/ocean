from enum import StrEnum
from typing import Literal

from pydantic.v1 import Field
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration

SESSION_ORIGINS = Literal[
    "webapp",
    "slack",
    "teams",
    "api",
    "linear",
    "jira",
    "automation",
    "cli",
    "desktop",
    "code_scan",
    "other",
]


class ObjectKind(StrEnum):
    SESSION = "session"
    PLAYBOOK = "playbook"
    KNOWLEDGE_NOTE = "knowledge-note"
    SECRET = "secret"


class SessionSelector(Selector):
    include_archived: bool = Field(
        default=False,
        alias="includeArchived",
        title="Include Archived",
        description="Whether to include archived sessions in the results.",
    )
    created_after_days: int | None = Field(
        default=30,
        alias="createdAfterDays",
        title="Created After (days)",
        description=(
            "Only sync sessions created in the last N days. Leave empty to sync "
            "every session, which can be slow for large organizations."
        ),
    )
    origins: list[SESSION_ORIGINS] | None = Field(
        default=None,
        title="Origins",
        description=(
            "Only sync sessions started from these origins, for example "
            '["api", "slack"]. Leave empty to sync every origin.'
        ),
    )
    only_managed_by_port: bool = Field(
        default=False,
        alias="onlyManagedByPort",
        title="Only Managed By Port",
        description="Only sync sessions created by this integration's actions.",
    )


class SessionResourceConfig(ResourceConfig):
    kind: Literal["session"] = Field(
        description="Devin session resource kind",
        title="Session",
    )
    selector: SessionSelector = Field(
        title="Session Selector",
        description="Selector for the session resource.",
    )


class PlaybookSelector(Selector):
    include_enterprise: bool = Field(
        default=False,
        alias="includeEnterprise",
        title="Include Enterprise",
        description="Whether to include enterprise-wide playbooks.",
    )


class PlaybookResourceConfig(ResourceConfig):
    kind: Literal["playbook"] = Field(
        description="Devin playbook resource kind",
        title="Playbook",
    )
    selector: PlaybookSelector = Field(
        title="Playbook Selector",
        description="Selector for the playbook resource.",
    )


class KnowledgeNoteResourceConfig(ResourceConfig):
    kind: Literal["knowledge-note"] = Field(
        description="Devin knowledge note resource kind",
        title="Knowledge Note",
    )


class SecretResourceConfig(ResourceConfig):
    kind: Literal["secret"] = Field(
        description="Devin secret (metadata only) resource kind",
        title="Secret",
    )


class DevinPortAppConfig(PortAppConfig):
    resources: list[
        SessionResourceConfig
        | PlaybookResourceConfig
        | KnowledgeNoteResourceConfig
        | SecretResourceConfig
    ] = Field(
        description="Resources for devin",
        title="Resources",
        default_factory=list,
    )  # type: ignore[assignment]


class DevinIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = DevinPortAppConfig
