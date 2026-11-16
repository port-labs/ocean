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


class ListModelDeploymentsOptions(ProjectIdentifier):
    pass


class EndpointScopedOptions(ProjectIdentifier):
    since_days: int | None = Field(default=30)
    endpoint_scopes: list[EndpointScope] = Field(default=[EndpointScope.AGENT])


class ListConversationsOptions(EndpointScopedOptions):
    pass


class ListResponsesOptions(EndpointScopedOptions):
    pass


class ListMemoryStoresOptions(ProjectIdentifier):
    pass


class ListSkillsOptions(ProjectIdentifier):
    pass


class ListToolboxesOptions(ProjectIdentifier):
    pass
