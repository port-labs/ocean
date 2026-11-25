from enum import StrEnum
from typing import Literal

from pydantic.v1 import Field

from port_ocean.core.handlers.port_app_config.models import (
    Selector,
    ResourceConfig,
    PortAppConfig,
)


class ObjectKind(StrEnum):
    AGENT = "agent"
    ENVIRONMENT = "environment"
    SESSION = "session"
    VAULT = "vault"
    MEMORY_STORE = "memory-store"
    SKILL = "skill"


class ArchivableSelector(Selector):
    include_archived: bool = Field(
        default=False,
        alias="includeArchived",
        title="Include Archived",
        description="Whether to include archived resources in the results.",
    )


class AgentSelector(ArchivableSelector):
    include_archived: bool = Field(
        default=False,
        alias="includeArchived",
        title="Include Archived",
        description=(
            "Whether to include archived agents in the results. Sessions keep "
            "referencing agents after they are archived, so enable this "
            "together with `includeSessionsOfArchivedResources` on the "
            "session kind to keep those sessions."
        ),
    )


class AgentResourceConfig(ResourceConfig):
    kind: Literal["agent"] = Field(
        description="Claude managed agent resource kind",
        title="Agent",
    )
    selector: AgentSelector = Field(
        title="Agent Selector",
        description="Selector for the agent resource.",
    )


class EnvironmentSelector(ArchivableSelector):
    include_archived: bool = Field(
        default=False,
        alias="includeArchived",
        title="Include Archived",
        description=(
            "Whether to include archived environments in the results. Sessions keep "
            "referencing environments after they are archived, so enable this "
            "together with `includeSessionsOfArchivedResources` on the "
            "session kind to keep those sessions."
        ),
    )


class EnvironmentResourceConfig(ResourceConfig):
    kind: Literal["environment"] = Field(
        description="Claude managed agent environment resource kind",
        title="Environment",
    )
    selector: EnvironmentSelector = Field(
        title="Environment Selector",
        description="Selector for the environment resource.",
    )


class SessionSelector(ArchivableSelector):
    include_archived: bool = Field(
        default=False,
        alias="includeArchived",
        title="Include Archived",
        description="Whether to include archived sessions in the results.",
    )
    include_sessions_of_archived_resources: bool = Field(
        default=False,
        alias="includeSessionsOfArchivedResources",
        title="Include Sessions Of Archived Resources",
        description=(
            "Whether to include sessions that reference an archived agent, "
            "environment, vault or memory store. When enabled, also set "
            "`includeArchived: true` on those kinds, otherwise these sessions "
            "point at resources that are not in the catalog."
        ),
    )


class SessionResourceConfig(ResourceConfig):
    kind: Literal["session"] = Field(
        description="Claude managed agent session resource kind",
        title="Session",
    )
    selector: SessionSelector = Field(
        title="Session Selector",
        description="Selector for the session resource.",
    )


class VaultSelector(ArchivableSelector):
    include_archived: bool = Field(
        default=False,
        alias="includeArchived",
        title="Include Archived",
        description=(
            "Whether to include archived vaults in the results. Sessions keep "
            "referencing vaults after they are archived, so enable this "
            "together with `includeSessionsOfArchivedResources` on the "
            "session kind to keep those sessions."
        ),
    )


class VaultResourceConfig(ResourceConfig):
    kind: Literal["vault"] = Field(
        description="Claude managed agent vault resource kind",
        title="Vault",
    )
    selector: VaultSelector = Field(
        title="Vault Selector",
        description="Selector for the vault resource.",
    )


class MemoryStoreSelector(ArchivableSelector):
    include_archived: bool = Field(
        default=False,
        alias="includeArchived",
        title="Include Archived",
        description=(
            "Whether to include archived memory stores in the results. Sessions keep "
            "referencing memory stores after they are archived, so enable this "
            "together with `includeSessionsOfArchivedResources` on the "
            "session kind to keep those sessions."
        ),
    )


class MemoryStoreResourceConfig(ResourceConfig):
    kind: Literal["memory-store"] = Field(
        description="Claude managed agent memory store resource kind",
        title="Memory Store",
    )
    selector: MemoryStoreSelector = Field(
        title="Memory Store Selector",
        description="Selector for the memory store resource.",
    )


class SkillResourceConfig(ResourceConfig):
    kind: Literal["skill"] = Field(
        description="Claude managed agent skill resource kind",
        title="Skill",
    )


class ClaudeManagedAgentsPortAppConfig(PortAppConfig):
    resources: list[
        AgentResourceConfig
        | EnvironmentResourceConfig
        | SessionResourceConfig
        | VaultResourceConfig
        | MemoryStoreResourceConfig
        | SkillResourceConfig
    ] = Field(
        description="Resources for claude-managed-agents",
        title="Resources",
        default_factory=list,
    )  # type: ignore[assignment]
