from enum import StrEnum
from typing import Literal

from pydantic.v1 import Field
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
)

FOUNDRY_ARM_PROJECT_KIND = "Microsoft.CognitiveServices/accounts/projects"


class ObjectKind(StrEnum):
    FOUNDRY_PROJECT = FOUNDRY_ARM_PROJECT_KIND
    AGENT = "foundry-agent"
    MODEL_DEPLOYMENT = "foundry-model-deployment"
    AGENT_VERSION = "foundry-agent-version"
    CONVERSATION = "foundry-conversation"
    RESPONSE = "foundry-response"
    MEMORY_STORE = "foundry-memory-store"


class FoundrySelector(Selector):
    query: str = Field(default="true")


class FoundryProjectResourceConfig(ResourceConfig):
    kind: Literal["Microsoft.CognitiveServices/accounts/projects"] = Field(
        title="Foundry project (ARM)"
    )
    selector: FoundrySelector = Field(default_factory=FoundrySelector)


class AgentSelector(FoundrySelector):
    include_versions: bool = Field(
        default=False,
        alias="includeVersions",
        title="Include versions",
        description="Fetch agent version metadata (additional API calls per agent).",
    )


class AgentResourceConfig(ResourceConfig):
    kind: Literal["foundry-agent"] = Field(title="Foundry agent")
    selector: AgentSelector = Field(default_factory=AgentSelector)


class ModelDeploymentResourceConfig(ResourceConfig):
    kind: Literal["foundry-model-deployment"] = Field(title="Foundry model deployment")
    selector: FoundrySelector = Field(default_factory=FoundrySelector)


class ConversationSelector(FoundrySelector):
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
    kind: Literal["foundry-conversation"] = Field(
        title="Foundry conversation",
        description=(
            "OpenAI conversation threads (metadata; token and participant rollups from response sync)."
        ),
    )
    selector: ConversationSelector = Field(default_factory=ConversationSelector)


class ResponseSelector(FoundrySelector):
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
    kind: Literal["foundry-response"] = Field(
        title="Foundry response",
        description=(
            "Foundry Responses API runs (usage, tool calls) linked to conversations."
        ),
    )
    selector: ResponseSelector = Field(default_factory=ResponseSelector)


class MemoryStoreResourceConfig(ResourceConfig):
    kind: Literal["foundry-memory-store"] = Field(title="Foundry memory store")
    selector: FoundrySelector = Field(default_factory=FoundrySelector)


class AgentVersionResourceConfig(ResourceConfig):
    kind: Literal["foundry-agent-version"] = Field(title="Foundry agent version")
    selector: FoundrySelector = Field(default_factory=FoundrySelector)
