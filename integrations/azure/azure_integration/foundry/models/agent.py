from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, TypeAdapter

from azure_integration.foundry.models.base import FoundryModel

_FEATURE_BY_KIND = {
    "hosted": "HostedAgents=V1Preview",
    "workflow": "WorkflowAgents=V1Preview",
    "external": "ExternalAgents=V1Preview",
    "voice": "VoiceAgents=V1Preview",
}


def features_header_for_kind(kind: str) -> dict[str, str] | None:
    feature = _FEATURE_BY_KIND.get(kind)
    return {"Foundry-Features": feature} if feature else None


class PromptAgentDefinition(FoundryModel):
    kind: Literal["prompt"] = "prompt"
    model: str | None = None
    tools: list[Any] = Field(default_factory=list)

    @property
    def features_header(self) -> dict[str, str] | None:
        return features_header_for_kind(self.kind)


class HostedAgentDefinition(FoundryModel):
    kind: Literal["hosted"] = "hosted"

    @property
    def features_header(self) -> dict[str, str] | None:
        return features_header_for_kind(self.kind)


# workflow / external / voice — no tools; extras via allow
class OtherAgentDefinition(FoundryModel):
    kind: Literal["workflow", "external", "voice"]

    @property
    def features_header(self) -> dict[str, str] | None:
        return features_header_for_kind(self.kind)


AgentDefinition = Annotated[
    PromptAgentDefinition | HostedAgentDefinition | OtherAgentDefinition,
    Field(discriminator="kind"),
]

_definition_adapter: TypeAdapter[AgentDefinition] = TypeAdapter(AgentDefinition)


def parse_agent_definition(data: dict[str, Any]) -> AgentDefinition:
    return _definition_adapter.validate_python(data)


class AgentVersion(FoundryModel):
    definition: AgentDefinition


class AgentVersions(FoundryModel):
    latest: AgentVersion


class Agent(FoundryModel):
    """GET /agents/{id} shape (+ ``__foundry*`` enrichments via extra=allow)."""

    versions: AgentVersions

    @property
    def latest_version(self) -> AgentVersion:
        return self.versions.latest

    @property
    def kind(self) -> str:
        return self.latest_version.definition.kind
