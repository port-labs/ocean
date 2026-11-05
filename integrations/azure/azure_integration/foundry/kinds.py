from enum import StrEnum
from typing import Literal

from pydantic.v1 import Field
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
)


class ObjectKind(StrEnum):
    FOUNDRY_PROJECT = "foundryProject"
    AGENT = "agent"
    MODEL_DEPLOYMENT = "model-deployment"
    AGENT_VERSION = "agent-version"
    CONVERSATION = "conversation"
    RESPONSE = "response"
    MEMORY_STORE = "memory-store"


class FoundryProjectSelector(Selector):
    pass


class FoundryProjectResourceConfig(ResourceConfig):
    kind: Literal["foundryProject"] = Field(title="Foundry project")
    selector: FoundryProjectSelector = Field(default_factory=FoundryProjectSelector)


class AgentSelector(Selector):
    include_versions: bool = Field(
        default=False,
        alias="includeVersions",
        title="Include versions",
        description="Fetch agent version metadata (additional API calls per agent).",
    )


class AgentResourceConfig(ResourceConfig):
    kind: Literal["agent"] = Field(title="Agent")
    selector: AgentSelector = Field(default_factory=AgentSelector)


class ModelDeploymentSelector(Selector):
    pass


class ModelDeploymentResourceConfig(ResourceConfig):
    kind: Literal["model-deployment"] = Field(title="Model deployment")
    selector: ModelDeploymentSelector = Field(default_factory=ModelDeploymentSelector)


class ConversationSelector(Selector):
    since_days: int = Field(
        default=365,
        ge=1,
        alias="sinceDays",
        title="Since (days)",
        description=(
            "Only list conversations created within this many days. "
            "Stops pagination once older conversations appear (with incremental cursor)."
        ),
    )


class ConversationResourceConfig(ResourceConfig):
    kind: Literal["conversation"] = Field(
        title="Conversation",
        description=(
            "OpenAI conversation threads (metadata; token and participant rollups from response sync)."
        ),
    )
    selector: ConversationSelector = Field(default_factory=ConversationSelector)


class ResponseSelector(Selector):
    since_days: int = Field(
        default=365,
        ge=1,
        alias="sinceDays",
        title="Since (days)",
        description=(
            "Only scan conversations created within this many days when listing responses. "
            "Response incremental cursor limits how far back each thread is read."
        ),
    )


class ResponseResourceConfig(ResourceConfig):
    kind: Literal["response"] = Field(
        title="Response",
        description=(
            "Foundry Responses API runs (usage, tool calls) linked to conversations."
        ),
    )
    selector: ResponseSelector = Field(default_factory=ResponseSelector)


class MemoryStoreSelector(Selector):
    pass


class MemoryStoreResourceConfig(ResourceConfig):
    kind: Literal["memory-store"] = Field(title="Memory store")
    selector: MemoryStoreSelector = Field(default_factory=MemoryStoreSelector)


class AgentVersionSelector(Selector):
    pass


class AgentVersionResourceConfig(ResourceConfig):
    kind: Literal["agent-version"] = Field(title="Agent version")
    selector: AgentVersionSelector = Field(default_factory=AgentVersionSelector)
