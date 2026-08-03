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


class ObjectKind(StrEnum):
    AGENT = "agent"
    ENVIRONMENT = "environment"
    SESSION = "session"
    VAULT = "vault"
    MEMORY_STORE = "memory-store"
    SKILL = "skill"


class AgentSelector(Selector):
    include_archived: bool = Field(
        default=False,
        alias="includeArchived",
        title="Include Archived",
        description="Whether to include archived agents in the results.",
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


class EnvironmentSelector(Selector):
    include_archived: bool = Field(
        default=False,
        alias="includeArchived",
        title="Include Archived",
        description="Whether to include archived environments in the results.",
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


class SessionSelector(Selector):
    include_archived: bool = Field(
        default=False,
        alias="includeArchived",
        title="Include Archived",
        description="Whether to include archived sessions in the results.",
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


class VaultSelector(Selector):
    include_archived: bool = Field(
        default=False,
        alias="includeArchived",
        title="Include Archived",
        description="Whether to include archived vaults in the results.",
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


class MemoryStoreSelector(Selector):
    include_archived: bool = Field(
        default=False,
        alias="includeArchived",
        title="Include Archived",
        description="Whether to include archived memory stores in the results.",
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


class ClaudeManagedAgentsIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = ClaudeManagedAgentsPortAppConfig
