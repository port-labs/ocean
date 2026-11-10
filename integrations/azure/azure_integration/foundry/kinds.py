from enum import StrEnum
from typing import Literal

from pydantic.v1 import BaseModel, Field
from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    Selector,
)

FOUNDRY_ARM_PROJECT_KIND = "Microsoft.CognitiveServices/accounts/projects"
DEFAULT_FOUNDRY_ARM_API_VERSION = "2025-06-01"


class ObjectKind(StrEnum):
    FOUNDRY_PROJECT = FOUNDRY_ARM_PROJECT_KIND
    AGENT = "foundry-agent"
    MODEL_DEPLOYMENT = "foundry-model-deployment"
    CONVERSATION = "foundry-conversation"
    RESPONSE = "foundry-response"
    MEMORY_STORE = "foundry-memory-store"


class FoundryProjectFilters(BaseModel):
    api_version: str = Field(
        default=DEFAULT_FOUNDRY_ARM_API_VERSION,
        alias="apiVersion",
        title="API Version",
        description="ARM API version used when discovering Foundry projects.",
    )


class FoundryProjectSelector(Selector):
    api_version: str = Field(
        default=DEFAULT_FOUNDRY_ARM_API_VERSION,
        alias="apiVersion",
        title="API Version",
        description="ARM API version used when querying Foundry projects.",
    )


class FoundrySelector(Selector):
    project: FoundryProjectFilters = Field(
        default_factory=FoundryProjectFilters,
        title="Project discovery",
        description="ARM filters used when discovering Foundry projects for this kind.",
    )


class FoundryProjectResourceConfig(ResourceConfig):
    kind: Literal["Microsoft.CognitiveServices/accounts/projects"] = Field(
        title="Foundry project (ARM)",
        description="Azure AI Foundry project discovered via ARM Cognitive Services accounts/projects.",
    )
    selector: FoundryProjectSelector = Field(
        default_factory=FoundryProjectSelector,
        title="Selector",
        description="Selector for Foundry project resources.",
    )


class AgentSelector(FoundrySelector):
    include_versions: bool = Field(
        default=False,
        alias="includeVersions",
        title="Include versions",
        description=(
            "Fetch full agent version history as __versions (additional API calls per "
            "agent). Use with itemsToParse on .__versions; parent .id is the agent "
            'identifier (e.g. identifier: .id + "/" + (.item.version | tostring)).'
        ),
    )


class AgentResourceConfig(ResourceConfig):
    kind: Literal["foundry-agent"] = Field(
        title="Foundry agent",
        description="Microsoft Foundry agent from the project Agent Control Plane.",
    )
    selector: AgentSelector = Field(
        default_factory=AgentSelector,
        title="Selector",
        description="Selector for Foundry agent resources.",
    )


class ModelDeploymentResourceConfig(ResourceConfig):
    kind: Literal["foundry-model-deployment"] = Field(
        title="Foundry model deployment",
        description="Model deployment visible to a Foundry project (project data-plane).",
    )
    selector: FoundrySelector = Field(
        default_factory=FoundrySelector,
        title="Selector",
        description="Selector for Foundry model deployment resources.",
    )


class ConversationSelector(FoundrySelector):
    since_days: int = Field(
        default=30,
        ge=1,
        le=30,
        alias="sinceDays",
        title="Since (days)",
        description=(
            "How far back to list conversations when syncing (1–30). Azure Foundry "
            "typically retains conversation/response state for about 30 days; values "
            "above that do not recover older threads. Stops pagination once older "
            "conversations appear (combined with the incremental cursor)."
        ),
    )


class ConversationResourceConfig(ResourceConfig):
    kind: Literal["foundry-conversation"] = Field(
        title="Foundry conversation",
        description=(
            "OpenAI conversation threads (metadata only; not full message "
            "transcripts). Conversation state in Azure is short-lived (~30 days)."
        ),
    )
    selector: ConversationSelector = Field(
        default_factory=ConversationSelector,
        title="Selector",
        description="Selector for Foundry conversation resources.",
    )


class ResponseSelector(FoundrySelector):
    since_days: int = Field(
        default=30,
        ge=1,
        le=30,
        alias="sinceDays",
        title="Since (days)",
        description=(
            "How far back to list project responses (1–30). Azure Foundry typically "
            "retains response data for about 30 days. Combined with the incremental "
            "cursor when stopping pagination."
        ),
    )


class ResponseResourceConfig(ResourceConfig):
    kind: Literal["foundry-response"] = Field(
        title="Foundry response",
        description=(
            "Foundry Responses API runs listed project-wide (usage, status, optional "
            "conversation relation). Response objects in Azure are retained for a "
            "limited period (~30 days), not indefinitely."
        ),
    )
    selector: ResponseSelector = Field(
        default_factory=ResponseSelector,
        title="Selector",
        description="Selector for Foundry response resources.",
    )


class MemoryStoreResourceConfig(ResourceConfig):
    kind: Literal["foundry-memory-store"] = Field(
        title="Foundry memory store",
        description="Persistent memory store for Foundry agents in a project.",
    )
    selector: FoundrySelector = Field(
        default_factory=FoundrySelector,
        title="Selector",
        description="Selector for Foundry memory store resources.",
    )
