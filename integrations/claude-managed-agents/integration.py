from enum import StrEnum
from typing import Literal

from pydantic import Field
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.integrations.base import BaseIntegration


class ObjectKind(StrEnum):
    AGENT = "agent"
    ENVIRONMENT = "environment"
    SESSION = "session"
    VAULT = "vault"
    MEMORY_STORE = "memory-store"
    SKILL = "skill"


class AgentResourceConfig(ResourceConfig):
    kind: Literal["agent"] = Field(
        description="Claude managed agent resource kind",
        title="Agent",
    )


class EnvironmentResourceConfig(ResourceConfig):
    kind: Literal["environment"] = Field(
        description="Claude managed agent environment resource kind",
        title="Environment",
    )


class SessionResourceConfig(ResourceConfig):
    kind: Literal["session"] = Field(
        description="Claude managed agent session resource kind",
        title="Session",
    )


class VaultResourceConfig(ResourceConfig):
    kind: Literal["vault"] = Field(
        description="Claude managed agent vault resource kind",
        title="Vault",
    )


class MemoryStoreResourceConfig(ResourceConfig):
    kind: Literal["memory-store"] = Field(
        description="Claude managed agent memory store resource kind",
        title="Memory Store",
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
