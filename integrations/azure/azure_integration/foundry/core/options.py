from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class EndpointScope(StrEnum):
    AGENT = "agent"
    PROJECT = "project"


class ProjectIdentifier(BaseModel):
    """Identifies a Foundry project for project-scoped exporters."""

    project_endpoint: str
    project_id: str


class ListAgentsOptions(ProjectIdentifier):
    include_versions: bool = False


class SingleAgentOptions(ProjectIdentifier):
    agent_id: str


class ListModelDeploymentsOptions(ProjectIdentifier):
    pass


class SingleModelDeploymentOptions(ProjectIdentifier):
    deployment_name: str


class EndpointScopedOptions(ProjectIdentifier):
    since_days: int | None = Field(default=30)
    endpoint_scopes: list[EndpointScope] = Field(default=[EndpointScope.AGENT])


class ListConversationsOptions(EndpointScopedOptions):
    pass


class ListResponsesOptions(EndpointScopedOptions):
    pass


class SingleEndpointScopedOptions(ProjectIdentifier):
    """GET one agent- or project-scoped resource (responses, conversations)."""

    resource_id: str
    endpoint_scope: EndpointScope = EndpointScope.AGENT
    agent_id: str | None = None


class SingleResponseOptions(SingleEndpointScopedOptions):
    pass


class SingleConversationOptions(SingleEndpointScopedOptions):
    pass


class ListMemoryStoresOptions(ProjectIdentifier):
    pass


class ListSkillsOptions(ProjectIdentifier):
    pass


class ListToolboxesOptions(ProjectIdentifier):
    pass
